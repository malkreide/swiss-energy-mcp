"""Die ruff-Version steht an genau einer Stelle — und bleibt dort.

Sie stand an zweien: `ruff>=0.4.0` im `[dev]`-Extra und
`pip install ruff==0.16.1` in `ci.yml`. Der CI-Schritt lief nach dem Install
des Extras und gewann gegen pyproject — der Wert dort war wirkungslos, und wer
die Gates lokal fuhr, benutzte die jeweils neueste Version statt der, gegen die
die CI prueft.

Beide Rueckfaelle sind still: Sie machen kein Gate rot, sie lassen es lediglich
mit einer anderen Version laufen als der, gegen die lokal geprueft wurde.
"""

from __future__ import annotations

import pathlib
import re
import tomllib

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_WORKFLOWS = _ROOT / ".github" / "workflows"

# Formen, in denen ein Schritt ein Paket eigenstaendig installiert. Die erste
# Fassung dieses Tests kannte nur `pip install ruff` und liess damit
# `pip install --upgrade ruff==…`, `pip install "ruff==…"`, `pip3 install`,
# `uv tool install` und `uv run --with ruff==…` durch — allesamt Formen, die
# den Pin genauso ueberstimmen. Aufgefallen ist das in einem Codex-Review.
_INSTALL_FORM = re.compile(
    r"(?:pip3?\s+install|python\s+-m\s+pip\s+install|uv\s+pip\s+install"
    r"|uv\s+tool\s+install|uv\s+add|pipx\s+install|--with)\b"
)
# ruff als eigenes Paket-Argument. Anfuehrungszeichen sind erlaubt, ein
# vorangehendes Wort-, Pfad- oder Bindestrich-Zeichen nicht: sonst zaehlten
# `ruff-lsp` und `scripts/ruff_helper.py` mit.
_RUFF_PAKET = re.compile(r"""(?<![\w./-])["']?ruff(?![\w-])""")

# Dieselbe Abgrenzung fuer einen Eintrag der Abhaengigkeitsliste. Hier stand
# `^ruff\b`, und das traf `ruff-lsp`: `\b` sitzt zwischen `f` und `-`, weil der
# Bindestrich kein Wortzeichen ist. Wer `ruff-lsp` ins dev-Extra aufnahm, bekam
# «genau ein ruff-Specifier erwartet, gefunden: ['ruff-lsp>=0.0.1',
# 'ruff==0.16.1']» — eine rote CI fuer etwas, das voellig in Ordnung ist. Die
# richtige Abgrenzung stand die ganze Zeit zwei Zeilen weiter oben.
_RUFF_SPEC = re.compile(r"ruff(?![\w-])")

# Der Kopf eines pre-commit-Eintrags, und das `rev:` darunter. Gesplittet wird
# am `- repo:`, damit ein `rev:` dem richtigen Hook zugeordnet wird — sonst
# gewaenne der erste `rev:` der Datei, also womoeglich der eines fremden Hooks.
# Die Verankerung auf `^\s*rev:` haelt ausserdem ein auskommentiertes
# `# rev: v0.9.9` heraus: nach dem Einzug kaeme dort ein `#`, kein `r`.
_PC_REPO = re.compile(r"^\s*-\s*repo:", re.MULTILINE)
_PC_REV = re.compile(r"""^\s*rev:\s*['"]?v?([^\s'"#]+)""", re.MULTILINE)


def _installiert_ruff(zeile: str) -> bool:
    """Installiert diese Zeile ruff als benanntes Paket?

    `pip install -e ".[dev]"` zieht ruff ebenfalls herein — das ist aber der
    richtige Weg und darf nicht anschlagen. Entscheidend ist deshalb, ob nach
    dem Install-Befehl ein eigenes Argument `ruff` steht.
    """
    treffer = _INSTALL_FORM.search(zeile)
    return bool(treffer) and bool(_RUFF_PAKET.search(zeile[treffer.end() :]))


def _workflow_dateien() -> list[pathlib.Path]:
    """Beide Endungen: GitHub laedt `*.yml` UND `*.yaml`."""
    return sorted([*_WORKFLOWS.glob("*.yml"), *_WORKFLOWS.glob("*.yaml")])


def _dev_abhaengigkeiten() -> list[str]:
    daten = tomllib.loads((_ROOT / "pyproject.toml").read_text())
    return daten["project"]["optional-dependencies"]["dev"]


def _hook_rev(text: str) -> str | None:
    """Die `rev:` des ruff-pre-commit-Hooks aus einer pre-commit-Konfiguration."""
    for block in _PC_REPO.split(text)[1:]:
        kopf, _, rest = block.partition("\n")
        if "ruff-pre-commit" not in kopf:
            continue
        treffer = _PC_REV.search(rest)
        if treffer:
            return treffer.group(1)
    return None


def test_ruff_ist_exakt_gepinnt() -> None:
    """Eine Spanne laesst lokalen Lauf und CI verschiedene Versionen fahren."""
    specs = [s for s in _dev_abhaengigkeiten() if _RUFF_SPEC.match(s)]
    assert len(specs) == 1, f"genau ein ruff-Specifier erwartet, gefunden: {specs}"
    assert re.fullmatch(r"ruff==\d+\.\d+\.\d+", specs[0]), (
        f"ruff muss als ruff==X.Y.Z gepinnt sein, gefunden {specs[0]!r}."
    )


def test_der_pin_ist_die_einzige_versionsquelle() -> None:
    """Kein Workflow darf ruff selbst installieren."""
    for workflow in _workflow_dateien():
        zeilen = [z for z in workflow.read_text().splitlines() if not z.lstrip().startswith("#")]
        treffer = [z.strip() for z in zeilen if _installiert_ruff(z)]
        assert not treffer, (
            f"{workflow.name} installiert ruff direkt ({treffer}). Dieser Schritt "
            "laeuft nach dem dev-Install und ueberstimmt den Pin in pyproject."
        )


def test_der_workflow_scan_findet_ueberhaupt_etwas() -> None:
    """Sichert die Pruefung oben gegen ein leeres Verzeichnis ab."""
    workflows = _workflow_dateien()
    assert len(workflows) >= 2, f"Workflow-Scan findet fast nichts: {workflows}"
    assert any("ruff check" in w.read_text() for w in workflows), (
        "kein Workflow ruft ruff auf — der Scan sucht am falschen Ort"
    )


def test_der_erkenner_kennt_die_gaengigen_installationsformen() -> None:
    """Der Scan ist nur so gut wie das, was er als Install erkennt.

    Ohne diese Tabelle ist die Zusicherung oben gruen, weil sie die Form nicht
    kennt — nicht, weil sie fehlt. Genau so war es: Die erste Fassung suchte
    woertlich nach `pip install ruff` und uebersah fuenf von sieben geprueften
    Schreibweisen.
    """
    muss_treffen = [
        "run: pip install ruff==0.16.1",
        "run: pip install --upgrade ruff==0.16.1",
        'run: pip install "ruff==0.16.1"',
        "run: pip install 'ruff==0.16.1'",
        "run: pip3 install ruff==0.16.1",
        "run: python -m pip install ruff==0.16.1",
        "run: uv pip install ruff==0.16.1 --system",
        "run: uv tool install ruff==0.16.1",
        "run: uv add ruff==0.16.1",
        "run: pipx install ruff==0.16.1",
        "run: uv run --with ruff==0.16.1 ruff check src/",
        "run: pip install ruff",
        "run: pip install pytest ruff==0.16.1",
        "run: pip install ruff[extra]==0.16.1",
    ]
    darf_nicht_treffen = [
        'run: pip install -e ".[dev]"',
        'run: uv pip install -e ".[dev]" --system',
        "run: ruff check src/ tests/ scripts/",
        "run: ruff format --check src/ tests/",
        "run: pip install ruff-lsp",
        "run: pip install uv",
        "run: python -m pip install --upgrade pip",
        "run: pip install build hatchling",
        "run: uv run --with pip-audit pip-audit",
        "run: python scripts/ruff_helper.py",
        "run: pip install -r requirements.txt",
        "name: Lint mit ruff",
    ]
    uebersehen = [z for z in muss_treffen if not _installiert_ruff(z)]
    assert not uebersehen, f"Erkenner uebersieht: {uebersehen}"
    fehlalarm = [z for z in darf_nicht_treffen if _installiert_ruff(z)]
    assert not fehlalarm, f"Erkenner schlaegt faelschlich an: {fehlalarm}"


def test_der_specifier_erkenner_trennt_ruff_von_ruff_lsp() -> None:
    """Die Gegenprobe zur Zusicherung oben.

    `test_ruff_ist_exakt_gepinnt` zaehlt die ruff-Eintraege im dev-Extra. Zaehlt
    der Erkenner zu viele mit, meldet es einen Fehler, den es nicht gibt; zaehlt
    er zu wenige, uebersieht es einen zweiten Specifier. Beides faellt am echten
    pyproject nicht auf, solange dort nur `ruff==X.Y.Z` steht — deshalb die
    Tabelle.
    """
    muss_treffen = ["ruff==0.16.1", "ruff>=0.4.0", "ruff", "ruff[extra]==0.16.1"]
    darf_nicht_treffen = ["ruff-lsp>=0.0.1", "ruff_helper", "pytest>=8.0", "respx>=0.21"]
    uebersehen = [s for s in muss_treffen if not _RUFF_SPEC.match(s)]
    assert not uebersehen, f"Erkenner uebersieht: {uebersehen}"
    fehlalarm = [s for s in darf_nicht_treffen if _RUFF_SPEC.match(s)]
    assert not fehlalarm, f"Erkenner schlaegt faelschlich an: {fehlalarm}"


def test_pre_commit_rev_passt_zum_pin() -> None:
    """Existiert ein ruff-Hook, muss seine `rev` den Pin wiederholen.

    pre-commit kann `pyproject.toml` nicht lesen und braucht die Zahl deshalb
    ein zweites Mal. Laufen die beiden auseinander, formatiert der Hook nach der
    einen und das Gate prueft nach der anderen Version — die Abweichungen, die
    dabei auftauchen, hat niemand verursacht.

    Dieses Repo hat heute keine pre-commit-Konfiguration. Der Test springt
    deshalb ab, statt still durchzugehen: Ein gruener Haken wuerde hier
    behaupten, etwas geprueft zu haben.
    """
    datei = _ROOT / ".pre-commit-config.yaml"
    if not datei.exists():
        pytest.skip("keine .pre-commit-config.yaml — nichts zu vergleichen")
    rev = _hook_rev(datei.read_text())
    assert rev is not None, "pre-commit-Konfiguration ohne ruff-pre-commit-Hook"
    spec = next(s for s in _dev_abhaengigkeiten() if _RUFF_SPEC.match(s))
    assert rev == spec.removeprefix("ruff=="), (
        f"pre-commit steht auf {rev}, das dev-Extra auf {spec} — beide im selben Commit bumpen."
    )


def test_der_hook_leser_ordnet_rev_und_repo_richtig_zu() -> None:
    """Ohne diese Tabelle waere die Zusicherung oben hier nicht pruefbar.

    Sie springt in diesem Repo ab, weil die Datei fehlt. Was sie benutzt, laesst
    sich trotzdem pruefen — und genau hier liegen die zwei Arten, still falsch
    zu lesen: Ein `rev:` dem falschen `repo:` zuzuordnen, und einen
    auskommentierten Wert fuer den echten zu halten.
    """
    ruff_block = (
        "  - repo: https://github.com/astral-sh/ruff-pre-commit\n"
        "    rev: v0.16.1\n"
        "    hooks:\n"
        "      - id: ruff-check\n"
    )
    fremder_block = (
        "  - repo: https://github.com/pre-commit/pre-commit-hooks\n"
        "    rev: v9.9.9\n"
        "    hooks:\n"
        "      - id: end-of-file-fixer\n"
    )
    faelle = {
        "allein": ("repos:\n" + ruff_block, "0.16.1"),
        "fremder Hook davor": ("repos:\n" + fremder_block + ruff_block, "0.16.1"),
        "auskommentiertes rev davor": (
            "repos:\n"
            "  - repo: https://github.com/astral-sh/ruff-pre-commit\n"
            "    # rev: v0.9.9  (vor dem Bump)\n"
            "    rev: v0.16.1\n"
            "    hooks:\n"
            "      - id: ruff-check\n",
            "0.16.1",
        ),
        "nur ein fremder Hook": ("repos:\n" + fremder_block, None),
    }
    falsch = {
        name: _hook_rev(text)
        for name, (text, erwartet) in faelle.items()
        if _hook_rev(text) != erwartet
    }
    assert not falsch, f"Hook-Leser liest falsch: {falsch}"
