"""Der SessionStart-Hook meldet einen veralteten Klon — und blockiert nie.

Ein veralteter Klon hat am 3.8.2026 zweimal eine rote CI erzeugt, deren
Ursache nicht im Diff stand: Die fehlenden Commits waren jeweils genau die,
die das Gate einfuehrten, an dem der Branch scheiterte. `.claude/hooks/`
prueft das beim Sessionstart.

Die Zusicherungen dieses Hooks sind unterschiedlich still, wenn sie brechen:

- Blockiert er, faellt es sofort auf — und er wird abgeschaltet. Danach
  schuetzt er gar nichts mehr. Deshalb steht "blockiert nie" hier vor allem
  anderen und wird fuer jeden Ausfallweg einzeln geprueft.
- Nimmt er `main` an, statt den Default-Branch zu ermitteln, bleibt er auf
  einem `master`-Repo einfach stumm. Das sieht aus wie "alles aktuell" und
  ist genau der Rueckfall, der einen Branch 15 Commits alt werden liess.
  `test_gegenprobe_*` neutralisiert die Ermittlung und zeigt, dass dieser
  Test dann faellt.
"""

from __future__ import annotations

import pathlib
import shutil
import subprocess
import time

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_HOOK = _ROOT / ".claude" / "hooks" / "session-start.sh"

# Ein Remote, der die Verbindung annimmt und dann nie antwortet — der Fall,
# den ein Hook ohne Timeout in einen haengenden Sessionstart uebersetzt.
_HAENGENDER_REMOTE = "ext::sleep 120"

_GIT_ENV = {
    "GIT_AUTHOR_NAME": "Test",
    "GIT_AUTHOR_EMAIL": "test@example.invalid",
    "GIT_COMMITTER_NAME": "Test",
    "GIT_COMMITTER_EMAIL": "test@example.invalid",
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_SYSTEM": "/dev/null",
    "HOME": "/nonexistent-home-fuer-tests",
    "PATH": "/usr/local/bin:/usr/bin:/bin",
}


def _git(cwd: pathlib.Path, *args: str) -> str:
    ergebnis = subprocess.run(
        ["git", *args],
        cwd=cwd,
        env=_GIT_ENV,
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    return ergebnis.stdout.strip()


class HookLauf:
    """Was ein Hook-Lauf hinterlassen hat: Ausgabe, Status, Dauer."""

    def __init__(self, fertig: subprocess.CompletedProcess[str], dauer: float) -> None:
        self.stdout = fertig.stdout
        self.stderr = fertig.stderr
        self.returncode = fertig.returncode
        self.dauer = dauer

    @property
    def schweigt(self) -> bool:
        return self.stdout.strip() == ""


def _hook(
    repo: pathlib.Path,
    *,
    payload: str = '{"hook_event_name":"SessionStart","source":"startup"}',
    skript: pathlib.Path | None = None,
    fetch_timeout: str = "5",
    ls_remote_timeout: str = "3",
) -> HookLauf:
    env = dict(_GIT_ENV)
    env["CLAUDE_PROJECT_DIR"] = str(repo)
    env["CLONE_CHECK_FETCH_TIMEOUT"] = fetch_timeout
    env["CLONE_CHECK_LS_REMOTE_TIMEOUT"] = ls_remote_timeout

    beginn = time.monotonic()
    fertig = subprocess.run(
        ["bash", str(skript or _HOOK)],
        cwd=repo,
        env=env,
        input=payload,
        capture_output=True,
        text=True,
        # Bewusst grosszuegig und ohne `check`: Ein Hook, der hier ins Timeout
        # laeuft, hat die Zusicherung schon gebrochen. Der Test soll das
        # benennen, nicht selbst haengen bleiben.
        timeout=60,
    )
    return HookLauf(fertig, time.monotonic() - beginn)


def _portfolio_repo(
    basis: pathlib.Path, default_branch: str = "main"
) -> tuple[pathlib.Path, pathlib.Path]:
    """Legt ein bare `origin` mit einem Commit an und klont es einmal.

    Rueckgabe: (Klon, Arbeitskopie zum Nachschieben von Commits).
    """
    remote = basis / "origin.git"
    _git(basis, "init", "--quiet", "--bare", "--initial-branch", default_branch, str(remote))

    quelle = basis / "quelle"
    quelle.mkdir()
    _git(quelle, "init", "--quiet", "--initial-branch", default_branch)
    (quelle / "README.md").write_text("erster Stand\n")
    _git(quelle, "add", "README.md")
    _git(quelle, "commit", "--quiet", "-m", "erster Commit")
    _git(quelle, "remote", "add", "origin", str(remote))
    _git(quelle, "push", "--quiet", "origin", default_branch)

    klon = basis / "klon"
    _git(basis, "clone", "--quiet", str(remote), str(klon))
    return klon, quelle


def _schiebe_nach(quelle: pathlib.Path, default_branch: str, anzahl: int) -> None:
    for n in range(anzahl):
        (quelle / f"neu-{n}.txt").write_text(f"Commit {n}\n")
        _git(quelle, "add", f"neu-{n}.txt")
        _git(quelle, "commit", "--quiet", "-m", f"neuer Commit {n}")
    _git(quelle, "push", "--quiet", "origin", default_branch)


@pytest.fixture
def repo(tmp_path: pathlib.Path) -> pathlib.Path:
    klon, _ = _portfolio_repo(tmp_path)
    return klon


# --------------------------------------------------------------------------
# Zusicherung 1: blockiert niemals
# --------------------------------------------------------------------------


def test_haengender_remote_laeuft_ins_timeout_statt_in_den_sessionstart(
    tmp_path: pathlib.Path,
) -> None:
    """Der wichtigste Fall: Remote nimmt an und antwortet nie.

    Ohne Timeout wartet `git fetch` hier unbegrenzt — der Sessionstart
    haengt, bis jemand abbricht. Mit Timeout kostet er ein paar Sekunden und
    geht still durch.
    """
    klon, _ = _portfolio_repo(tmp_path)
    _git(klon, "config", "protocol.ext.allow", "always")
    _git(klon, "remote", "set-url", "origin", _HAENGENDER_REMOTE)

    lauf = _hook(klon, fetch_timeout="2", ls_remote_timeout="2")

    assert lauf.returncode == 0
    assert lauf.schweigt
    # Budget: ls-remote (2s) + fetch (2s) + Aufraeumen. 20s ist grosszuegig
    # und faellt trotzdem, sobald ein Netzzugriff ohne Limit laeuft — der
    # Remote schweigt zwei Minuten.
    assert lauf.dauer < 20, f"Hook brauchte {lauf.dauer:.1f}s — Timeout greift nicht"


def test_unerreichbarer_remote_blockiert_nicht(repo: pathlib.Path) -> None:
    _git(repo, "remote", "set-url", "origin", str(repo / "gibt-es-nicht.git"))
    lauf = _hook(repo)
    assert lauf.returncode == 0
    assert lauf.schweigt


def test_gescheiterter_fetch_meldet_keine_alte_zahl(tmp_path: pathlib.Path) -> None:
    """Scheitert der Fetch, schweigt der Hook — statt aus altem Stand zu reden.

    Der Klon traegt hier zwei Reste eines frueheren, erfolgreichen Fetch:
    `refs/remotes/origin/main` steht drei Commits voraus, `FETCH_HEAD` vier
    (vom `feature`-Branch). Beide sind ohne Netz beliebig alt. Eine
    Implementierung, die gegen die lokalen Remote-Refs zaehlt statt gegen das
    Ergebnis eines geglueckten Fetch, meldet an dieser Stelle eine Zahl, fuer
    die sie keine Deckung hat.
    """
    klon, quelle = _portfolio_repo(tmp_path)

    _git(quelle, "checkout", "--quiet", "-b", "feature")
    for n in range(4):
        (quelle / f"f-{n}.txt").write_text(f"Feature {n}\n")
        _git(quelle, "add", f"f-{n}.txt")
        _git(quelle, "commit", "--quiet", "-m", f"Feature {n}")
    _git(quelle, "push", "--quiet", "origin", "feature")
    _git(quelle, "checkout", "--quiet", "main")
    _schiebe_nach(quelle, "main", 3)

    _git(klon, "fetch", "--quiet", "origin", "main")
    _git(klon, "fetch", "--quiet", "origin", "feature")
    assert _git(klon, "rev-list", "--count", "HEAD..refs/remotes/origin/main") == "3"
    assert _git(klon, "rev-list", "--count", "HEAD..FETCH_HEAD") == "4"

    _git(klon, "remote", "set-url", "origin", str(tmp_path / "gibt-es-nicht.git"))

    lauf = _hook(klon)

    assert lauf.returncode == 0
    assert lauf.schweigt, f"Hook meldete eine Zahl ohne geglueckten Fetch: {lauf.stdout!r}"


def test_repo_ganz_ohne_remote_blockiert_nicht(repo: pathlib.Path) -> None:
    _git(repo, "remote", "remove", "origin")
    lauf = _hook(repo)
    assert lauf.returncode == 0
    assert lauf.schweigt


def test_verzeichnis_ohne_git_blockiert_nicht(tmp_path: pathlib.Path) -> None:
    kein_repo = tmp_path / "kein-repo"
    kein_repo.mkdir()
    lauf = _hook(kein_repo)
    assert lauf.returncode == 0
    assert lauf.schweigt


def test_repo_ohne_commits_blockiert_nicht(tmp_path: pathlib.Path) -> None:
    leer = tmp_path / "leer"
    leer.mkdir()
    _git(leer, "init", "--quiet", "--initial-branch", "main")
    lauf = _hook(leer)
    assert lauf.returncode == 0
    assert lauf.schweigt


def test_detached_head_schweigt(tmp_path: pathlib.Path) -> None:
    """Wer einen einzelnen Commit auscheckt, bisect faehrt oder einen Tag
    ansieht, steht absichtlich neben dem Branch-Verlauf. Ein Rueckstand ist
    dort keine Meldung wert — auf demselben Klon mit Branch meldet der Hook
    sehr wohl, sonst pruefte dieser Test bloss ein stummes Skript."""
    klon, quelle = _portfolio_repo(tmp_path)
    _schiebe_nach(quelle, "main", 2)

    assert "2 Commits" in _hook(klon).stdout

    _git(klon, "checkout", "--quiet", "--detach", "HEAD")
    lauf = _hook(klon)

    assert lauf.returncode == 0
    assert lauf.schweigt, f"Hook meldete bei detached HEAD: {lauf.stdout!r}"


def test_detached_head_kostet_keinen_netzzugriff(tmp_path: pathlib.Path) -> None:
    """Die Pruefung steht vor dem Fetch, nicht dahinter.

    Nachgestellt mit einem Remote, der annimmt und nie antwortet: Wuerde
    zuerst gefetcht, liefe der Hook in die Timeouts und braeuchte Sekunden,
    obwohl das Ergebnis schon feststeht.
    """
    klon, _ = _portfolio_repo(tmp_path)
    _git(klon, "config", "protocol.ext.allow", "always")
    _git(klon, "remote", "set-url", "origin", _HAENGENDER_REMOTE)
    _git(klon, "checkout", "--quiet", "--detach", "HEAD")

    lauf = _hook(klon, fetch_timeout="5", ls_remote_timeout="3")

    assert lauf.returncode == 0
    assert lauf.schweigt
    assert lauf.dauer < 2, f"Hook brauchte {lauf.dauer:.1f}s — er fetcht vor der Pruefung"


def test_hook_veraendert_den_arbeitsbaum_nicht(tmp_path: pathlib.Path) -> None:
    """Er meldet, er repariert nicht. Ein Hook, der beim Sessionstart merged,
    ueberrascht mitten in unfertiger Arbeit."""
    klon, quelle = _portfolio_repo(tmp_path)
    _schiebe_nach(quelle, "main", 3)
    vorher = _git(klon, "rev-parse", "HEAD")

    lauf = _hook(klon)

    assert lauf.returncode == 0
    assert _git(klon, "rev-parse", "HEAD") == vorher
    assert _git(klon, "status", "--porcelain") == ""


def test_ohne_timeout_binary_bleibt_das_limit_bestehen(tmp_path: pathlib.Path) -> None:
    """Fehlt `timeout` aus den coreutils, greift der Rueckfall — nicht: kein Limit.

    Der Hook bekommt einen PATH ohne `timeout`; der haengende Remote muss
    trotzdem abgeschnitten werden.
    """
    if shutil.which("timeout") is None:  # pragma: no cover - Umgebung ohne coreutils
        pytest.skip("`timeout` fehlt bereits, der Rueckfall ist der Normalfall")

    klon, _ = _portfolio_repo(tmp_path)
    _git(klon, "config", "protocol.ext.allow", "always")
    _git(klon, "remote", "set-url", "origin", _HAENGENDER_REMOTE)

    ohne_timeout = tmp_path / "bin-ohne-timeout"
    ohne_timeout.mkdir()
    # `sh` braucht git fuer den ext::-Transport, `bash` der Hook selbst.
    for werkzeug in ("bash", "sh", "git", "sed", "tr", "cat", "head", "ssh", "sleep"):
        pfad = shutil.which(werkzeug)
        if pfad:
            (ohne_timeout / werkzeug).symlink_to(pfad)

    env = dict(_GIT_ENV)
    env["PATH"] = str(ohne_timeout)
    env["CLAUDE_PROJECT_DIR"] = str(klon)
    env["CLONE_CHECK_FETCH_TIMEOUT"] = "2"
    env["CLONE_CHECK_LS_REMOTE_TIMEOUT"] = "2"

    beginn = time.monotonic()
    fertig = subprocess.run(
        # Absoluter Pfad: Der eingeengte PATH gilt fuer das, was der Hook
        # findet — nicht fuer die Frage, womit er gestartet wird.
        [str(ohne_timeout / "bash"), str(_HOOK)],
        cwd=klon,
        env=env,
        input='{"source":"startup"}',
        capture_output=True,
        text=True,
        timeout=60,
    )
    dauer = time.monotonic() - beginn

    assert fertig.returncode == 0
    assert fertig.stdout.strip() == ""
    assert dauer < 25, f"Rueckfall ohne `timeout` brauchte {dauer:.1f}s"


# --------------------------------------------------------------------------
# Zusicherung 2: Ausgabe nur, wenn Commits fehlen
# --------------------------------------------------------------------------


def test_schweigt_wenn_der_klon_aktuell_ist(repo: pathlib.Path) -> None:
    lauf = _hook(repo)
    assert lauf.returncode == 0
    assert lauf.schweigt, f"Hook meldete bei 0 fehlenden Commits: {lauf.stdout!r}"


def test_schweigt_wenn_der_klon_voraus_ist(repo: pathlib.Path) -> None:
    """Eigene, noch nicht gepushte Commits sind kein Rueckstand."""
    (repo / "eigene-arbeit.txt").write_text("lokal\n")
    _git(repo, "add", "eigene-arbeit.txt")
    _git(repo, "commit", "--quiet", "-m", "eigene Arbeit")

    lauf = _hook(repo)

    assert lauf.returncode == 0
    assert lauf.schweigt


def test_meldet_die_zahl_der_fehlenden_commits(tmp_path: pathlib.Path) -> None:
    klon, quelle = _portfolio_repo(tmp_path)
    _schiebe_nach(quelle, "main", 3)

    lauf = _hook(klon)

    assert lauf.returncode == 0
    assert "3 Commits" in lauf.stdout
    assert "origin/main" in lauf.stdout


def test_ein_einzelner_commit_wird_im_singular_gemeldet(tmp_path: pathlib.Path) -> None:
    klon, quelle = _portfolio_repo(tmp_path)
    _schiebe_nach(quelle, "main", 1)

    lauf = _hook(klon)

    assert "1 Commit\n" in lauf.stdout
    assert "1 Commits" not in lauf.stdout


def test_feature_branch_erbt_den_rueckstand_seiner_basis(tmp_path: pathlib.Path) -> None:
    """Der Fall vom 3.8.2026: gearbeitet wird auf einem Branch, veraltet ist
    die Basis, an der er haengt."""
    klon, quelle = _portfolio_repo(tmp_path)
    _git(klon, "checkout", "--quiet", "-b", "claude/irgendein-feature")
    (klon / "feature.txt").write_text("Arbeit\n")
    _git(klon, "add", "feature.txt")
    _git(klon, "commit", "--quiet", "-m", "Feature")
    _schiebe_nach(quelle, "main", 4)

    lauf = _hook(klon)

    assert "4 Commits" in lauf.stdout
    assert "claude/irgendein-feature" in lauf.stdout


@pytest.mark.parametrize("quelle_source", ["compact", "clear"])
def test_schweigt_bei_compact_und_clear(tmp_path: pathlib.Path, quelle_source: str) -> None:
    """SessionStart feuert auch mitten in der Arbeit — dort ist ein
    Netz-Roundtrip nur Latenz."""
    klon, quelle = _portfolio_repo(tmp_path)
    _schiebe_nach(quelle, "main", 5)

    lauf = _hook(klon, payload=f'{{"source":"{quelle_source}"}}')

    assert lauf.returncode == 0
    assert lauf.schweigt


def test_meldet_ohne_payload_auf_stdin(tmp_path: pathlib.Path) -> None:
    """Kein oder unlesbarer Payload heisst pruefen, nicht schweigen."""
    klon, quelle = _portfolio_repo(tmp_path)
    _schiebe_nach(quelle, "main", 2)

    lauf = _hook(klon, payload="")

    assert "2 Commits" in lauf.stdout


# --------------------------------------------------------------------------
# Zusicherung 3: der Default-Branch wird ermittelt, nicht angenommen
# --------------------------------------------------------------------------


def test_master_als_default_branch_wird_erkannt(tmp_path: pathlib.Path) -> None:
    """Drei Repos im Portfolio heissen ihren Default-Branch `master`.

    Wer `main` annimmt, bekommt dort «couldn't find remote ref main», haelt
    das fuer ein Netzproblem und arbeitet auf genau dem veralteten Klon
    weiter, vor dem der Hook warnen sollte.
    """
    klon, quelle = _portfolio_repo(tmp_path, default_branch="master")
    _schiebe_nach(quelle, "master", 15)

    lauf = _hook(klon)

    assert "15 Commits" in lauf.stdout
    assert "origin/master" in lauf.stdout
    assert "origin/main" not in lauf.stdout


def test_ohne_lokalen_origin_head_wird_der_remote_gefragt(tmp_path: pathlib.Path) -> None:
    """Nach `clone --depth` oder bei einem von Hand angelegten Remote fehlt
    `refs/remotes/origin/HEAD`. Dann ist `ls-remote --symref` die Quelle —
    und immer noch keine Annahme."""
    klon, quelle = _portfolio_repo(tmp_path, default_branch="master")
    _schiebe_nach(quelle, "master", 2)
    _git(klon, "symbolic-ref", "--delete", "refs/remotes/origin/HEAD")

    lauf = _hook(klon)

    assert "2 Commits" in lauf.stdout
    assert "origin/master" in lauf.stdout


# --------------------------------------------------------------------------
# Gegenproben: Zusicherung einzeln neutralisieren, Test muss fallen
# --------------------------------------------------------------------------


def _ohne(zeile_alt: str, zeile_neu: str, ziel: pathlib.Path) -> pathlib.Path:
    text = _HOOK.read_text()
    assert zeile_alt in text, f"Gegenprobe greift ins Leere: {zeile_alt!r} steht nicht im Hook"
    ziel.write_text(text.replace(zeile_alt, zeile_neu))
    return ziel


def test_gegenprobe_hartverdrahtetes_main_faellt_auf_master(tmp_path: pathlib.Path) -> None:
    """Neutralisiert die Branch-Ermittlung — `test_master_als_default_branch_
    wird_erkannt` muss dann stumm bleiben, sonst prueft er nichts."""
    klon, quelle = _portfolio_repo(tmp_path, default_branch="master")
    _schiebe_nach(quelle, "master", 15)

    kaputt = _ohne(
        'case "$symref" in\norigin/*) default_branch="${symref#origin/}" ;;\nesac',
        'default_branch="main"',
        tmp_path / "hook-mit-main.sh",
    )

    lauf = _hook(klon, skript=kaputt)

    assert lauf.schweigt, "Ohne Branch-Ermittlung meldet der Hook trotzdem — der Test prueft nichts"


def test_gegenprobe_ohne_null_abbruch_meldet_der_hook_auch_bei_aktuell(
    repo: pathlib.Path, tmp_path: pathlib.Path
) -> None:
    """Neutralisiert das Schweigen bei 0 — `test_schweigt_wenn_der_klon_
    aktuell_ist` muss dann fallen."""
    kaputt = _ohne(
        "0) exit 0 ;;\nesac",
        "esac",
        tmp_path / "hook-ohne-null.sh",
    )

    lauf = _hook(repo, skript=kaputt)

    assert "0 Commits" in lauf.stdout, "Ohne den 0-Abbruch schweigt der Hook immer noch"


def test_gegenprobe_ohne_timeout_haengt_der_hook(tmp_path: pathlib.Path) -> None:
    """Neutralisiert das Limit — der haengende Remote muss den Hook dann
    ueber das Budget hinaus festhalten."""
    klon, _ = _portfolio_repo(tmp_path)
    _git(klon, "config", "protocol.ext.allow", "always")
    _git(klon, "remote", "set-url", "origin", _HAENGENDER_REMOTE)

    # Beide Mechanismen ausbauen: Nur den `timeout`-Zweig zu entfernen
    # genuegt nicht, dann greift der Poll-Rueckfall und schneidet ebenfalls
    # ab. Hier laeuft der Aufruf danach wirklich unbegrenzt.
    text = _HOOK.read_text()
    for alt, neu in (
        ("if command -v timeout >/dev/null 2>&1; then", "if true; then"),
        ('timeout -k 1 "$secs" "$@"', '"$@"'),
    ):
        assert alt in text, f"Gegenprobe greift ins Leere: {alt!r}"
        text = text.replace(alt, neu)
    kaputt = tmp_path / "hook-ohne-timeout.sh"
    kaputt.write_text(text)

    with pytest.raises(subprocess.TimeoutExpired):
        subprocess.run(
            ["bash", str(kaputt)],
            cwd=klon,
            env={**_GIT_ENV, "CLAUDE_PROJECT_DIR": str(klon)},
            input='{"source":"startup"}',
            capture_output=True,
            text=True,
            timeout=15,
        )
