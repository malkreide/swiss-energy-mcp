# SessionStart-Hook: Klon-Aktualitaet

`session-start.sh` meldet beim Sessionstart, wie viele Commits der
ausgecheckte Stand hinter dem Default-Branch von `origin` liegt. Liegt er
nicht zurueck, gibt er nichts aus.

Registriert in `../settings.json` unter `hooks.SessionStart`. JSON kennt keine
Kommentare — die Begruendung steht deshalb hier und im Kopf des Skripts.

## Warum

Ein veralteter Klon hat am 3.8.2026 zweimal eine rote CI erzeugt, deren
Ursache nicht im Diff stand. Die fehlenden Commits waren jeweils genau die,
die das Gate einfuehrten, an dem der Branch scheiterte: Der Branch fiel
durch eine Pruefung, die er lokal noch gar nicht kannte, und die Fehlersuche
lief in den geaenderten Dateien statt in der Historie. Die Pruefung kostet
eine Sekunde und ersetzt eine Fehlersuche in den falschen Dateien.

## Zusicherungen

Nach Wichtigkeit geordnet — `tests/test_session_start_hook.py` haelt jede
davon fest, statt sie zu behaupten.

1. **Der Hook blockiert die Session niemals.** Kein Netz, kein `origin`,
   ein Remote, der nicht antwortet, detached HEAD, ein Repo ohne Commits,
   gar kein Git-Repo — jeder Fall geht still durch und endet mit Status 0.
   Deshalb steht im Skript bewusst kein `set -e`: Ein Hook, der bei
   Netzproblemen die Arbeit anhaelt, wird nach dem zweiten Mal abgeschaltet
   und schuetzt danach gar nichts.
2. **Kurzes Timeout auf jeden Netzzugriff.** `git fetch` bekommt 5 Sekunden,
   ein allfaelliges `git ls-remote` 3 (`CLONE_CHECK_FETCH_TIMEOUT`,
   `CLONE_CHECK_LS_REMOTE_TIMEOUT`). Fehlt `timeout` aus den coreutils,
   faellt das Skript auf einen Hintergrundprozess mit Poll-Schleife zurueck,
   statt das Limit stillschweigend fallen zu lassen. `GIT_TERMINAL_PROMPT=0`
   und `ssh -o BatchMode=yes` verhindern, dass eine Passwortabfrage den
   Sessionstart haengen laesst.
3. **Ausgabe nur, wenn tatsaechlich Commits fehlen.** Bei 0 schweigt er.
4. **Der Default-Branch wird ermittelt, nicht als `main` angenommen.**
   Drei Repos im Portfolio (`openlex-mcp`, `swiss-courts-mcp`,
   `swisstopo-mcp`) heissen ihn `master`; genau diese Annahme hat schon
   einmal einen Branch 15 Commits alt werden lassen, weil
   `git fetch origin main` dort mit «couldn't find remote ref main»
   scheitert und das wie ein Netzproblem aussieht. Erste Quelle ist
   `refs/remotes/origin/HEAD` — den hat der Remote beim Klonen gesetzt, das
   ist keine Annahme und kostet kein Netz. Fehlt er (etwa nach
   `git clone --depth` oder bei einem von Hand angelegten Remote), fragt das
   Skript den Remote per `git ls-remote --symref`. Ist er so nicht zu
   ermitteln, schweigt der Hook — ein Fetch auf einen geratenen Branch
   meldet entweder nichts oder etwas Falsches.

## Was er nicht tut

Er aendert den Arbeitsbaum nicht. Kein `pull`, kein `merge`, kein `checkout`
— er nennt nur die Zahl und den Befehl, mit dem man sie loswird.

Bei `source` `compact` und `clear` feuert `SessionStart` mitten in der
Arbeit; dort steigt der Hook sofort aus, weil ein Netz-Roundtrip dann nur
Latenz waere. Gelesen wird das aus dem Hook-Payload auf stdin.

## Lokal ausprobieren

```bash
.claude/hooks/session-start.sh            # im Repo, ohne Payload
echo '{"source":"startup"}' | .claude/hooks/session-start.sh
pytest tests/test_session_start_hook.py -v
```
