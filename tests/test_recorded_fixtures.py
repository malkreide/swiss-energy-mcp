"""Jedes Werkzeug, gefahren aus einer aufgezeichneten Antwort.

Die handgeschriebenen Stubs in `conftest.py` pruefen die *Fehler*-Pfade — ein
Timeout, ein 5xx, `success: false`, eine leere Trefferliste —, die sich nicht auf
Zuruf aufzeichnen lassen und als Erfindung in Ordnung sind. Was sie nicht
koennen: die Form einer Erfolgs-Antwort belegen. Sie stimmen mit dem ueberein,
was ihr Autor annahm.

Genau daran ist es hier gescheitert: `conftest.dataset()` baute eine CKAN-Zeile
mit `notes` — wie der Code sie las —, waehrend opendata.swiss das Feld
`description` nennt. `energy_search_bfe_datasets` lieferte zu jedem Datensatz
eine leere Beschreibung, und die Suite blieb gruen.

Zwei Hosts, aber zehn Abfrageformen. Aufgezeichnet ist deshalb eine Antwort je
**Abfrage** und nicht je Endpunkt oder je Werkzeug: zwei Werkzeuge, die dieselbe
Abfrage schicken, teilen sich eine Datei, und `energy_location_profile` schickt
seine fuenf per `asyncio.gather` in unbestimmter Reihenfolge. Der Dispatcher
unten ordnet deshalb nach der Anfrage zu und nicht nach der Reihenfolge.

Herkunft, Datum, Auswahlregel und SHA-256 je Datei stehen in
`tests/fixtures/PROVENANCE.md`; neu aufzeichnen mit
`python scripts/record_fixtures.py`.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from typing import Any

import httpx
import pytest
import respx

from swiss_energy_mcp.api_client import GEOADMIN_BASE, OPENDATA_SWISS_BASE
from tests.fixture_data import (
    fixture_json,
    fixture_text,
    name_fuer,
    provenance,
    recorded_names,
    recorder,
)

MONT_CROSIN = {"lat": 47.1800, "lon": 7.0300, "radius_m": 10000}

# Werkzeug → (Eingabeklasse, Eingabe, Aufzeichnungen, die es lesen soll).
# Bewusst noch einmal hingeschrieben und nicht aus dem Recorder-PLAN abgeleitet:
# die Tests sollen eine eigene Aussage machen. Dass beide Listen dieselben
# Dateien meinen, prueft `test_der_recorder_kennt_dieselben_aufzeichnungen`.
WERKZEUGE: dict[str, tuple[str, dict[str, Any], list[str]]] = {
    "energy_find_power_plants": (
        "PowerPlantInput",
        dict(MONT_CROSIN),
        ["identify_elektrizitaetsproduktionsanlagen.json"],
    ),
    "energy_find_wind_turbines": (
        "LocationInput",
        dict(MONT_CROSIN),
        ["identify_windenergieanlagen.json"],
    ),
    "energy_find_hydro_plants": (
        "LocationInput",
        dict(MONT_CROSIN),
        ["identify_statistik_wasserkraftanlagen.json"],
    ),
    "energy_find_pv_installations": (
        "LocationInput",
        dict(MONT_CROSIN),
        ["identify_photovoltaik_grossanlagen.json"],
    ),
    "energy_find_biogas_plants": (
        "LocationInput",
        dict(MONT_CROSIN),
        ["identify_biogasanlagen.json"],
    ),
    "energy_solar_potential": (
        "LocationInput",
        dict(MONT_CROSIN),
        ["identify_solarenergie_eignung_daecher.json"],
    ),
    "energy_find_energy_cities": (
        "EnergyCityInput",
        {"name": "Zürich"},
        ["find_energiestaedte_name.json"],
    ),
    "energy_location_profile": (
        "LocationInput",
        dict(MONT_CROSIN),
        [
            "identify_elektrizitaetsproduktionsanlagen.json",
            "identify_windenergieanlagen.json",
            "identify_statistik_wasserkraftanlagen.json",
            "identify_photovoltaik_grossanlagen.json",
            "identify_energiestaedte.json",
        ],
    ),
    "energy_search_bfe_datasets": (
        "SearchInput",
        {"query": "wasserkraft", "limit": 10},
        ["package_search_rows10.json"],
    ),
    "energy_check_status": (
        "",
        {},
        ["find_energiestaedte_name.json", "package_search_rows1.json"],
    ),
}

# `energy_find_energy_cities` mit Koordinaten statt Namen — dieselbe Funktion,
# andere Abfrageform, deshalb eine eigene Aufzeichnung.
CITIES_PER_KOORDINATE = ("EnergyCityInput", dict(MONT_CROSIN), ["identify_energiestaedte.json"])

ALLE_AUFZEICHNUNGEN = sorted(
    {n for _, _, namen in WERKZEUGE.values() for n in namen} | set(CITIES_PER_KOORDINATE[2])
)

# Die CKAN-Aufzeichnungen — die, in denen der Feldname `description` steckt.
KATALOG = ["package_search_rows10.json", "package_search_rows1.json"]


# --------------------------------------------------------------------------
# Der Dispatcher: jede Anfrage bekommt die Aufzeichnung ihrer eigenen Abfrage
# --------------------------------------------------------------------------
@pytest.fixture
def quelle():
    """Beantwortet beide Hosts aus den Aufzeichnungen und protokolliert mit.

    Nach der *Anfrage* zugeordnet, nicht nach der Reihenfolge: sonst waere
    `energy_location_profile` mit seinem `asyncio.gather` ein Gluecksspiel und
    die Zuordnung im gruenen Fall zufaellig richtig.
    """
    protokoll: list[httpx.URL] = []

    def antwort(request: httpx.Request) -> httpx.Response:
        protokoll.append(request.url)
        return httpx.Response(200, text=fixture_text(name_fuer(request.url)))

    with respx.mock:
        respx.get(url__startswith=GEOADMIN_BASE).mock(side_effect=antwort)
        respx.get(url__startswith=OPENDATA_SWISS_BASE).mock(side_effect=antwort)
        yield protokoll


def _zeilen(name: str) -> int:
    """Die Zahl der Trefferzeilen einer Aufzeichnung — GeoAdmin wie CKAN.

    GeoAdmin legt sie unter `results`, CKAN eine Ebene tiefer unter
    `result.results`.
    """
    daten = fixture_json(name)
    if isinstance(daten.get("results"), list):
        return len(daten["results"])
    return len(daten["result"]["results"])


async def _fahre(tool, ctx, werkzeug: str, klasse: str, eingabe: dict[str, Any]):
    """Ruft ein Werkzeug ueber die `tool`-Fixture aus `conftest.py`."""
    from swiss_energy_mcp import models

    fn = tool(werkzeug)
    if not klasse:
        return await fn(ctx)
    return await fn(getattr(models, klasse)(**eingabe), ctx)


# --------------------------------------------------------------------------
# Herkunft
# --------------------------------------------------------------------------
def test_provenance_nennt_ein_brauchbares_aufnahmedatum():
    """Eine Aufzeichnung ohne Datum ist eine undatierte Behauptung ueber die Quelle."""
    treffer = re.search(r"Aufgezeichnet am \*\*(\d{4}-\d{2}-\d{2})\*\*", provenance())
    assert treffer, "PROVENANCE.md nennt kein Aufnahmedatum im erwarteten Format"
    wann = dt.date.fromisoformat(treffer.group(1))
    assert wann <= dt.datetime.now(dt.UTC).date(), "Aufnahmedatum liegt in der Zukunft"


def test_jede_fixture_steht_in_der_provenance():
    """Sonst waechst der Ordner und der Nachweis bleibt zurueck."""
    text = provenance()
    fehlend = [n for n in recorded_names() if f"## `{n}`" not in text]
    assert not fehlend, f"ohne Eintrag in PROVENANCE.md: {fehlend}"


def test_jede_abfrageform_hat_eine_aufzeichnung():
    """Bewacht die Regel selbst — je Abfrage statt je Endpunkt.

    Zwei Hosts, zehn Abfrageformen: «eine Antwort je externem Endpunkt» waere
    mit zwei Dateien erfuellt und truege fast nichts.
    """
    fehlend = sorted(set(ALLE_AUFZEICHNUNGEN) - set(recorded_names()))
    assert not fehlend, f"Abfrageformen ohne Aufzeichnung: {fehlend}"


def test_keine_aufzeichnung_liegt_unbenutzt_herum():
    """Die Gegenrichtung — eine Datei, die niemand liest, belegt nichts."""
    ueberzaehlig = sorted(set(recorded_names()) - set(ALLE_AUFZEICHNUNGEN))
    assert not ueberzaehlig, f"von keinem Test gelesen: {ueberzaehlig}"


def test_der_recorder_kennt_dieselben_aufzeichnungen():
    """Recorder und Tests duerfen nicht auseinanderlaufen.

    Laedt `scripts/record_fixtures.py` als Modul — `main()` wird nicht gerufen,
    es geht keine Anfrage raus.
    """
    werkzeuge_im_plan = {a.werkzeug for a in recorder().PLAN}
    assert werkzeuge_im_plan == set(WERKZEUGE), (
        "Recorder und Testtabelle fahren verschiedene Werkzeuge"
    )


def test_die_namensregel_trifft_jede_aufzeichnung():
    """Der Dispatcher benennt nach derselben Regel wie der Recorder.

    Waere sie hier eine zweite Kopie, liefe sie irgendwann auseinander und der
    Dispatcher lieferte stillschweigend die falsche Datei — was wie ein
    gruener Test aussaehe.
    """
    aus_provenance = re.findall(r"- \*\*URL:\*\* `([^`]+)`", provenance())
    assert aus_provenance, "PROVENANCE.md nennt keine URLs"
    for url in aus_provenance:
        assert name_fuer(url) in recorded_names(), f"{url} → {name_fuer(url)} fehlt"


# --------------------------------------------------------------------------
# Der Fund: opendata.swiss nennt die Beschreibung `description`
# --------------------------------------------------------------------------
@pytest.mark.parametrize("name", KATALOG)
def test_der_katalog_nennt_die_beschreibung_description(name):
    """Der Fund, der diesen Ordner rechtfertigt.

    Der Code las `notes` — den Namen aus dem CKAN-Kern. opendata.swiss liefert
    das Feld unter `description`. Ergebnis: zu jedem Datensatz eine leere
    Beschreibung, produktiv, bei gruener Suite.
    """
    zeilen = fixture_json(name)["result"]["results"]
    assert zeilen, f"{name} traegt keine Trefferzeilen — neu aufzeichnen"
    for zeile in zeilen:
        assert "notes" not in zeile, "der Katalog kennt `notes` — Annahme neu pruefen"
        assert "description" in zeile, f"{zeile.get('name')} ohne `description`"


async def test_die_beschreibung_kommt_im_ergebnis_an(tool, ctx, quelle):
    """Und das ist die Zusicherung, die den Fund festhaelt.

    Sie faellt, sobald wieder ein Feldname geraten wird: aus der aufgezeichneten
    Antwort muss beim Modell eine nicht-leere Beschreibung ankommen.
    """
    klasse, eingabe, _ = WERKZEUGE["energy_search_bfe_datasets"]
    antwort = await _fahre(tool, ctx, "energy_search_bfe_datasets", klasse, eingabe)
    assert antwort.results, "keine Datensaetze aus der Aufzeichnung"
    leer = [d["title"] for d in antwort.results if not (d["notes"] or "").strip()]
    assert not leer, f"{len(leer)} von {len(antwort.results)} Datensaetze ohne Beschreibung"
    # Und sie muss auch im Markdown stehen, nicht nur im strukturierten Feld.
    assert antwort.results[0]["notes"][:40] in antwort.summary


def test_titel_und_beschreibung_sind_sprach_dicts():
    """Der Grund, warum es `_localized` gibt — ein `str()` ergaebe `{'de': …}`."""
    zeile = fixture_json("package_search_rows10.json")["result"]["results"][0]
    for feld in ("title", "description"):
        assert isinstance(zeile[feld], dict), f"{feld} ist kein Sprach-Dict"
        assert "de" in zeile[feld], f"{feld} fuehrt kein Deutsch"


# --------------------------------------------------------------------------
# Der zweite Fund: die «leichtgewichtige» Statusabfrage war es nicht
# --------------------------------------------------------------------------
async def test_die_statusabfrage_verzichtet_auf_die_geometrie(tool, ctx, quelle):
    """`energy_check_status` nennt sich leichtgewichtig — jetzt ist es das auch.

    Ohne `returnGeometry=false` liefert GeoAdmin die Gemeindegeometrie mit:
    159 656 statt 574 Bytes fuer denselben einen Treffer, den das Werkzeug nur
    zaehlt. Gemessen am 15.08.2026. Diese Zusicherung liest die tatsaechlich
    gestellte Anfrage, nicht das Ergebnis — im Ergebnis waere der Unterschied
    unsichtbar.
    """
    await _fahre(tool, ctx, "energy_check_status", "", {})
    finds = [u for u in quelle if u.path.endswith("/find")]
    assert finds, "die Statusabfrage hat GeoAdmin gar nicht gefragt"
    for url in finds:
        assert url.params.get("returnGeometry") == "false", f"Geometrie angefordert: {url}"


def test_beide_find_abfragen_teilen_sich_eine_aufzeichnung():
    """Weil sie zeichengleich sind — das ist der Beleg, kein Zufall.

    Solange `energy_check_status` seine Anfrage von Hand baut, kann sie von der
    aus `find_geoadmin_by_name()` abweichen. Zwei Dateien statt einer waeren das
    sichtbare Zeichen dafuer.
    """
    nachweis = provenance()
    block = nachweis.split("## `find_energiestaedte_name.json`", 1)[1]
    kopf = block.split("## ", 1)[0]
    assert "`energy_check_status`" in kopf and "`energy_find_energy_cities`" in kopf, kopf


# --------------------------------------------------------------------------
# Die Werkzeuge, jedes an seiner eigenen Antwort
# --------------------------------------------------------------------------
@pytest.mark.parametrize("werkzeug", sorted(w for w in WERKZEUGE if w != "energy_check_status"))
async def test_jedes_werkzeug_liest_seine_aufgezeichnete_antwort(tool, ctx, quelle, werkzeug):
    """Der eigentliche Punkt: jede Abfrage bekommt *ihre* Antwort.

    Alle mit derselben zu bedienen hiesse, die Aufzeichnung gegen eine Abfrage
    zu halten, die sie nicht beantwortet — genau der Fehler, den eine Fixture je
    Abfrage verhindern soll.
    """
    klasse, eingabe, namen = WERKZEUGE[werkzeug]
    antwort = await _fahre(tool, ctx, werkzeug, klasse, eingabe)
    assert antwort.count > 0, f"{werkzeug} liefert nichts aus der Aufzeichnung"
    assert antwort.match_type == "exact"
    assert antwort.notes is None, f"{werkzeug} meldet einen Leer-Hinweis trotz Treffern"
    assert len(quelle) == len(namen), f"{werkzeug} schickte {len(quelle)} statt {len(namen)}"
    # Und es muessen die Zeilen *seiner* Aufzeichnung sein, nicht irgendwelche:
    # alle `identify`-Antworten sind gleich gebaut, ein Werkzeug mit der
    # falschen Datei faellt sonst nicht auf. Das Profil zaehlt fuenf Layer
    # zusammen und wird deshalb eigens geprueft.
    if werkzeug != "energy_location_profile":
        assert antwort.count == sum(_zeilen(n) for n in namen), (
            f"{werkzeug} las offenbar eine fremde Aufzeichnung"
        )


async def test_die_energiestaedte_gehen_je_nach_eingabe_woandershin(tool, ctx, quelle):
    """Mit `name` an `find`, mit Koordinaten an `identify` — zwei Abfrageformen.

    Eine Aufzeichnung belegte nur die halbe Sache, und ein Test, der beide mit
    derselben Datei bedient, merkte eine Vertauschung nicht.
    """
    klasse, eingabe, _ = CITIES_PER_KOORDINATE
    await _fahre(tool, ctx, "energy_find_energy_cities", klasse, eingabe)
    assert [u.path.rsplit("/", 1)[-1] for u in quelle] == ["identify"]

    quelle.clear()
    klasse, eingabe, _ = WERKZEUGE["energy_find_energy_cities"]
    await _fahre(tool, ctx, "energy_find_energy_cities", klasse, eingabe)
    assert [u.path.rsplit("/", 1)[-1] for u in quelle] == ["find"]


async def test_das_standortprofil_zaehlt_alle_fuenf_layer(tool, ctx, quelle):
    """Fuenf Layer, per `asyncio.gather` in unbestimmter Reihenfolge.

    Die Zahlen im Profil muessen die der fuenf Aufzeichnungen sein — und zwar
    Zeile fuer Zeile in der Tabelle. «Die Zahl kommt irgendwo im Text vor» war
    die erste Fassung, und die Gegenprobe zeigte, warum das zu wenig ist: ein
    Dispatcher, der allen dieselbe Datei gibt, kam damit durch.
    """
    klasse, eingabe, namen = WERKZEUGE["energy_location_profile"]
    antwort = await _fahre(tool, ctx, "energy_location_profile", klasse, eingabe)
    assert len(quelle) == 5

    fuer = {n.removeprefix("identify_").removesuffix(".json"): _zeilen(n) for n in namen}
    tabelle = {
        "Windenergie": fuer["windenergieanlagen"],
        "Wasserkraft": fuer["statistik_wasserkraftanlagen"],
        "PV-Grossanlagen": fuer["photovoltaik_grossanlagen"],
        "Energiestädte": fuer["energiestaedte"],
    }
    for beschriftung, anzahl in tabelle.items():
        assert f"| {beschriftung} | {anzahl} |" in antwort.summary, (
            f"«{beschriftung}» steht nicht mit {anzahl} im Profil:\n{antwort.summary}"
        )
    # Die Produktionsanlagen teilt das Profil in PV-Einzelanlagen und Uebrige
    # auf; zusammen muessen sie die Zeilen der Aufzeichnung ergeben.
    aufgeteilt = [
        int(m)
        for m in re.findall(
            r"\| (?:Photovoltaik \(Einzelanlagen\)|Übrige Produktionsanlagen) \| (\d+) \|",
            antwort.summary,
        )
    ]
    assert len(aufgeteilt) == 2
    assert sum(aufgeteilt) == fuer["elektrizitaetsproduktionsanlagen"]


async def test_die_windanlage_liest_ihre_turbinen_aus_dem_xml(tool, ctx, quelle):
    """Ein Feature traegt die Turbinendaten als XML-Zeichenkette in `turbines`.

    Ein Stub, der das Feld weglaesst, laesst die Zeile «Turbine:» einfach
    verschwinden — ohne dass ein Test faellt.
    """
    assert (
        "<tur_manufacturer>"
        in fixture_json("identify_windenergieanlagen.json")["results"][0]["attributes"]["turbines"]
    ), "die Aufzeichnung traegt kein Turbinen-XML mehr"

    klasse, eingabe, _ = WERKZEUGE["energy_find_wind_turbines"]
    antwort = await _fahre(tool, ctx, "energy_find_wind_turbines", klasse, eingabe)
    assert "**Turbine:**" in antwort.summary
    assert "Nabenhöhe" in antwort.summary


async def test_der_status_meldet_beide_apis_verfuegbar(tool, ctx, quelle):
    antwort = await _fahre(tool, ctx, "energy_check_status", "", {})
    assert len(antwort.apis) == 2
    assert all(a.available for a in antwort.apis), [a.detail for a in antwort.apis]


# --------------------------------------------------------------------------
# Die Gegenrichtung
# --------------------------------------------------------------------------
@respx.mock
async def test_eine_leere_trefferliste_bleibt_eine_leere_trefferliste(tool, ctx):
    """`results: []` ist eine Aussage der Quelle: dort steht nichts.

    Das darf nicht als Fehler herauskommen — sonst kann das Modell einen echten
    Negativtreffer nicht von einem Ausfall unterscheiden. Und es muss einen
    naechsten Schritt nennen, sonst meldet das Modell nur «keine Treffer».
    """
    respx.get(url__startswith=GEOADMIN_BASE).mock(
        return_value=httpx.Response(200, text=json.dumps({"results": []}))
    )
    klasse, eingabe, _ = WERKZEUGE["energy_find_wind_turbines"]
    antwort = await _fahre(tool, ctx, "energy_find_wind_turbines", klasse, eingabe)
    assert antwort.count == 0
    assert antwort.match_type == "none"
    assert antwort.notes and "radius_m" in antwort.notes


@respx.mock
async def test_ein_abbruch_bleibt_ein_fehler(tool, ctx, ohne_wartezeit):
    """Und die andere Haelfte: ein Ausfall darf nicht als leeres Ergebnis erscheinen."""
    respx.get(url__startswith=GEOADMIN_BASE).mock(side_effect=httpx.ConnectError("weg"))
    klasse, eingabe, _ = WERKZEUGE["energy_find_wind_turbines"]
    with pytest.raises(ValueError):
        await _fahre(tool, ctx, "energy_find_wind_turbines", klasse, eingabe)
