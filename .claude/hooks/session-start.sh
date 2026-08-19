#!/usr/bin/env bash
#
# SessionStart-Hook: meldet, wie viele Commits der ausgecheckte Stand hinter
# dem Default-Branch von origin liegt. Schweigt, wenn nichts fehlt.
#
# WARUM: Ein veralteter Klon hat am 3.8.2026 zweimal eine rote CI erzeugt,
# deren Ursache nicht im Diff stand — die fehlenden Commits waren jeweils
# genau die, die das Gate einfuehrten, an dem der Branch scheiterte. Die
# Pruefung kostet eine Sekunde und ersetzt eine Fehlersuche in den falschen
# Dateien. Siehe .claude/hooks/README.md.
#
# OBERSTE REGEL: Dieser Hook blockiert die Session NIEMALS. Kein Netz, kein
# Remote, detached HEAD, flatterndes DNS — jeder Fall geht still durch und
# endet mit Status 0. Deshalb hier bewusst KEIN `set -e` und kein `set -o
# pipefail`: ein Hook, der bei Netzproblemen die Arbeit anhaelt, wird nach
# dem zweiten Mal abgeschaltet und schuetzt danach gar nichts.

set -u

# Ab hier kann nichts mehr fehlschlagen, ohne dass wir still enden.
trap 'exit 0' ERR

LS_REMOTE_TIMEOUT="${CLONE_CHECK_LS_REMOTE_TIMEOUT:-3}"
FETCH_TIMEOUT="${CLONE_CHECK_FETCH_TIMEOUT:-5}"

# Git darf unter keinen Umstaenden interaktiv nachfragen — ein Prompt auf
# Credentials oder einen unbekannten Host-Key haengt den Sessionstart, bis
# das Timeout greift, und im schlimmsten Fall darueber hinaus.
export GIT_TERMINAL_PROMPT=0
export GIT_ASKPASS=true
export SSH_ASKPASS=true
export GIT_CONFIG_PARAMETERS="${GIT_CONFIG_PARAMETERS:+$GIT_CONFIG_PARAMETERS }'credential.helper='"
export GIT_SSH_COMMAND="${GIT_SSH_COMMAND:-ssh} -o BatchMode=yes -o ConnectTimeout=3"

# Laeuft `cmd` mit hartem Zeitlimit. Ohne coreutils-`timeout` faellt die
# Funktion auf einen Hintergrundprozess mit Poll-Schleife zurueck, statt das
# Limit stillschweigend fallen zu lassen — genau der Fall, in dem ein
# haengendes fetch den Sessionstart blockieren wuerde.
run_limited() {
  local secs="$1"
  shift
  if command -v timeout >/dev/null 2>&1; then
    timeout -k 1 "$secs" "$@"
    return $?
  fi

  "$@" &
  local pid=$!
  local waited=0
  while kill -0 "$pid" 2>/dev/null; do
    if [ "$waited" -ge "$secs" ]; then
      kill -TERM "$pid" 2>/dev/null
      sleep 1
      kill -KILL "$pid" 2>/dev/null
      wait "$pid" 2>/dev/null
      return 124
    fi
    sleep 1
    waited=$((waited + 1))
  done
  wait "$pid"
}

# `source` aus dem Hook-Payload lesen: bei `compact` und `clear` feuert
# SessionStart mitten in der Arbeit, da ist ein Netz-Roundtrip nur Latenz.
payload=""
if [ ! -t 0 ]; then
  payload="$(run_limited 2 cat 2>/dev/null)" || payload=""
fi
case "$(printf '%s' "$payload" | tr -d ' \t\n' | sed -n 's/.*"source":"\([a-z]*\)".*/\1/p')" in
compact | clear) exit 0 ;;
esac

cd "${CLAUDE_PROJECT_DIR:-.}" 2>/dev/null || exit 0
command -v git >/dev/null 2>&1 || exit 0
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || exit 0

# Unborn HEAD (frisches Repo ohne Commit) — nichts zu vergleichen.
git rev-parse --verify --quiet HEAD >/dev/null 2>&1 || exit 0

# Kein origin -> kein Vergleichspunkt.
git config --get remote.origin.url >/dev/null 2>&1 || exit 0

# Default-Branch ERMITTELN, nicht "main" annehmen: mindestens ein Repo im
# Portfolio nutzt "master" (openlex-mcp, swiss-courts-mcp, swisstopo-mcp),
# und genau diese Annahme hat schon einmal einen Branch 15 Commits alt
# werden lassen — `git fetch origin main` scheitert dort mit "couldn't find
# remote ref main", was wie ein Netzproblem aussieht.
#
# Erste Quelle ist das lokale refs/remotes/origin/HEAD: das hat der Remote
# beim Klonen gesetzt, es ist also keine Annahme, und es kostet kein Netz.
default_branch=""
symref="$(git symbolic-ref --quiet --short refs/remotes/origin/HEAD 2>/dev/null)" || symref=""
case "$symref" in
origin/*) default_branch="${symref#origin/}" ;;
esac

# Fehlt der lokale Zeiger (kommt bei `git clone --depth` oder manuell
# angelegten Remotes vor), den Remote fragen.
if [ -z "$default_branch" ]; then
  ls_remote="$(run_limited "$LS_REMOTE_TIMEOUT" git ls-remote --symref origin HEAD 2>/dev/null)" || ls_remote=""
  default_branch="$(printf '%s\n' "$ls_remote" | sed -n 's|^ref: refs/heads/\([^[:space:]]*\)[[:space:]].*|\1|p' | head -n 1)" || default_branch=""
fi

# Nicht ermittelbar -> still durchgehen. Kein Rueckfall auf "main": ein
# Fetch auf den falschen Branch meldet entweder nichts oder etwas Falsches.
[ -n "$default_branch" ] || exit 0

run_limited "$FETCH_TIMEOUT" git fetch --quiet origin "$default_branch" >/dev/null 2>&1 || exit 0

# Ausgewertet wird nur nach erfolgreichem Fetch — der Abbruch eine Zeile
# hoeher ist dafuer der eigentliche Schutz. FETCH_HEAD statt
# refs/remotes/origin/<branch>, weil letzteres auch ohne Netz dasteht und
# dann eine beliebig alte Zahl liefert; dass git 2.43 FETCH_HEAD schon beim
# Start eines Fetch leert, ist ein zweiter Boden, kein Ersatz fuer den
# Abbruch.
behind="$(git rev-list --count HEAD..FETCH_HEAD 2>/dev/null)" || exit 0
case "$behind" in
'' | *[!0-9]*) exit 0 ;;
0) exit 0 ;;
esac

current="$(git rev-parse --abbrev-ref HEAD 2>/dev/null)" || current="HEAD"
if [ "$current" = "HEAD" ]; then
  current="detached HEAD"
fi

if [ "$behind" = "1" ]; then
  commit_wort="Commit"
else
  commit_wort="Commits"
fi

cat <<EOF
[Klon-Aktualitaet] Der ausgecheckte Stand ($current) liegt $behind $commit_wort
hinter origin/$default_branch.

Fehlende Commits sind eine haeufige Ursache fuer rote CI, deren Grund nicht im
Diff steht: der Branch scheitert an einem Gate, das er noch gar nicht kennt.
Vor der Arbeit den Default-Branch einholen:

    git fetch origin $default_branch && git merge origin/$default_branch

Dieser Hinweis blockiert nichts.
EOF

exit 0
