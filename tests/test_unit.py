"""Unit tests for pure helpers: coordinates, formatting, models, egress guard."""

from __future__ import annotations

from pathlib import Path

import pytest

from swiss_energy_mcp import api_client
from swiss_energy_mcp.api_client import (
    ALLOWED_HOSTS,
    IDENTIFY_TOLERANCE,
    assert_url_allowed,
    radius_to_map_extent,
    resolve_allowed_ip,
    wgs84_to_lv95,
)
from swiss_energy_mcp.formatting import (
    clean_label,
    format_power_value,
    format_wind_turbines,
    format_year,
)
from swiss_energy_mcp.settings import Settings

# ---------------------------------------------------------------------------
# Coordinate conversion
# ---------------------------------------------------------------------------


class TestCoordinateConversion:
    def test_zurich_center(self):
        e, n = wgs84_to_lv95(47.3769, 8.5417)
        assert 2680000 < e < 2690000
        assert 1245000 < n < 1252000

    def test_bern(self):
        e, n = wgs84_to_lv95(46.9480, 7.4474)
        assert 2597000 < e < 2603000
        assert 1199000 < n < 1205000

    def test_eastward_increases(self):
        e_west, _ = wgs84_to_lv95(47.0, 7.0)
        e_east, _ = wgs84_to_lv95(47.0, 9.0)
        assert e_east > e_west

    def test_northward_increases(self):
        _, n_south = wgs84_to_lv95(46.0, 8.0)
        _, n_north = wgs84_to_lv95(47.5, 8.0)
        assert n_north > n_south

    def test_output_types(self):
        e, n = wgs84_to_lv95(47.0, 8.0)
        assert isinstance(e, float) and isinstance(n, float)


class TestMapExtent:
    def test_extent_contains_center(self):
        r = radius_to_map_extent(47.3769, 8.5417, 5000)
        assert r["xmin"] < r["e"] < r["xmax"]
        assert r["ymin"] < r["n"] < r["ymax"]

    def test_extent_size(self):
        r = radius_to_map_extent(47.0, 8.0, 10000)
        assert abs((r["xmax"] - r["xmin"]) - 20000) < 10

    def test_all_keys(self):
        r = radius_to_map_extent(47.0, 8.0, 5000)
        assert {"xmin", "ymin", "xmax", "ymax", "e", "n"} <= set(r)

    def test_tolerance_is_500(self):
        assert IDENTIFY_TOLERANCE == 500
        assert isinstance(IDENTIFY_TOLERANCE, int)


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


class TestFormatting:
    def test_power_kw(self):
        assert "18.81 kW" in format_power_value(18.81, "kW")

    def test_power_kw_to_mw(self):
        result = format_power_value(1500, "kW")
        assert "MW" in result and "1.50" in result

    def test_power_none(self):
        assert format_power_value(None) == "k.A."

    def test_power_comma_string(self):
        assert "kW" in format_power_value("18,81", "kW")

    def test_year_int(self):
        assert format_year(2021) == "2021"

    def test_year_none(self):
        assert format_year(None) == "k.A."

    def test_clean_label_removes_tags(self):
        assert clean_label("<b>Zürich</b>") == "Zürich"

    def test_wind_turbine_xml_parsing(self):
        from tests.conftest import wind_turbine_feature

        out = format_wind_turbines([wind_turbine_feature()], "Test")
        assert "Vestas" in out and "V90" in out and "100 m" in out


# ---------------------------------------------------------------------------
# Egress guard (SEC-004 / SEC-021)
# ---------------------------------------------------------------------------


class TestEgressGuard:
    def test_allowed_host_passes(self):
        assert_url_allowed("https://api3.geo.admin.ch/rest/services")

    def test_opendata_host_passes(self):
        assert_url_allowed("https://opendata.swiss/api/3/action/package_search")

    def test_ckan_opendata_host_passes(self):
        assert_url_allowed("https://ckan.opendata.swiss/api/3/action/package_search")

    def test_non_https_rejected(self):
        with pytest.raises(ValueError, match="HTTPS"):
            assert_url_allowed("http://api3.geo.admin.ch/x")

    def test_disallowed_host_rejected(self):
        with pytest.raises(ValueError, match="Allow-List"):
            assert_url_allowed("https://evil.example.com/x")

    def test_localhost_rejected(self):
        with pytest.raises(ValueError):
            assert_url_allowed("https://localhost/x")

    def test_metadata_host_rejected(self):
        with pytest.raises(ValueError, match="Allow-List"):
            assert_url_allowed("https://169.254.169.254/latest/meta-data")

    def test_allowed_hosts_frozenset(self):
        assert isinstance(ALLOWED_HOSTS, frozenset)
        assert "api3.geo.admin.ch" in ALLOWED_HOSTS


# ---------------------------------------------------------------------------
# DNS pinning (SEC-005)
# ---------------------------------------------------------------------------


def _patch_dns(monkeypatch, ip: str) -> None:
    """Force getaddrinfo (as used by api_client) to resolve to a single IP."""
    info = [(2, 1, 6, "", (ip, 443))]
    monkeypatch.setattr(api_client.socket, "getaddrinfo", lambda *a, **k: info)


class TestDnsPinning:
    _PUBLIC_IP = "185.12.64.10"

    def test_resolve_returns_pinned_ip(self, monkeypatch):
        _patch_dns(monkeypatch, self._PUBLIC_IP)
        assert resolve_allowed_ip("api3.geo.admin.ch") == self._PUBLIC_IP

    def test_resolve_rejects_rebinding_to_private(self, monkeypatch):
        # Allow-listed host whose DNS answer points at a private address.
        _patch_dns(monkeypatch, "10.1.2.3")
        with pytest.raises(ValueError, match="IP-Adresse"):
            resolve_allowed_ip("api3.geo.admin.ch")

    def test_resolve_rejects_unlisted_host(self):
        with pytest.raises(ValueError, match="Allow-List"):
            resolve_allowed_ip("evil.example.com")

    async def test_backend_connects_to_pinned_ip(self, monkeypatch):
        """The backend must open the socket to the validated IP, not the hostname."""
        captured: dict[str, object] = {}

        async def fake_connect(self, host, port, **kwargs):
            captured["host"] = host
            captured["port"] = port
            return object()

        _patch_dns(monkeypatch, self._PUBLIC_IP)
        monkeypatch.setattr(api_client.AutoBackend, "connect_tcp", fake_connect)

        backend = api_client._PinnedDNSBackend()
        await backend.connect_tcp("api3.geo.admin.ch", 443)

        assert captured["host"] == self._PUBLIC_IP
        assert captured["port"] == 443


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


class TestSettings:
    def test_defaults(self):
        s = Settings(_env_file=None)
        assert s.transport == "stdio"
        assert s.host == "127.0.0.1"
        assert s.port == 8000

    def test_cors_origins_from_csv(self):
        s = Settings(_env_file=None, cors_origins="https://a.test,https://b.test")
        assert s.cors_origins == ["https://a.test", "https://b.test"]

    # Der Test darueber geht am Befund vorbei, und zwar der Bauart nach: ein
    # direktes Schluesselwort umgeht die EnvSettingsSource, und genau dort lag
    # der Absturz. Die naechsten drei fahren deshalb durch die Umgebung.

    @pytest.mark.parametrize(
        ("raw", "erwartet"),
        [
            # Genau der Wert, den README und .env.example nennen.
            ("https://claude.ai", ["https://claude.ai"]),
            (
                "https://a.test,https://b.test",
                ["https://a.test", "https://b.test"],
            ),
            (" https://a.test , https://b.test ", ["https://a.test", "https://b.test"]),
            ("*", ["*"]),
            # Die JSON-Form ist die einzige, die vor der Behebung durchkam.
            ('["https://a.test","https://b.test"]', ["https://a.test", "https://b.test"]),
        ],
    )
    def test_cors_origins_aus_der_umgebung(self, monkeypatch, raw, erwartet):
        monkeypatch.setenv("SWISS_ENERGY_CORS_ORIGINS", raw)
        assert Settings(_env_file=None).cors_origins == erwartet

    def test_allowed_hosts_aus_der_umgebung(self, monkeypatch):
        # Dieselbe Mechanik, dasselbe Feldpaar — der Docstring in settings.py
        # nennt fuer allowed_hosts eine kommagetrennte Liste als Beispiel.
        monkeypatch.setenv("SWISS_ENERGY_ALLOWED_HOSTS", "mcp.example.ch,mcp.example.ch:443")
        assert Settings(_env_file=None).allowed_hosts == [
            "mcp.example.ch",
            "mcp.example.ch:443",
        ]

    def test_die_ausgelieferte_env_vorlage_startet(self, tmp_path, monkeypatch):
        """`.env.example` woertlich als `.env` — die Datei sagt selbst, man
        solle sie kopieren. Vor der Behebung starb genau das mit einem
        SettingsError, weil `SWISS_ENERGY_CORS_ORIGINS=https://claude.ai`
        kein JSON ist."""
        vorlage = Path(__file__).resolve().parent.parent / ".env.example"
        text = vorlage.read_text(encoding="utf-8")
        ziel = tmp_path / ".env"
        ziel.write_text(text, encoding="utf-8")

        # Sonst prueft der Test nur noch, dass irgendeine Vorlage laedt: in der
        # JSON-Form laeuft er auch ohne die Behebung durch. Beide READMEs nennen
        # die Komma-Form, also faehrt die Vorlage sie auch.
        zeile = next(z for z in text.splitlines() if z.startswith("SWISS_ENERGY_CORS_ORIGINS="))
        assert not zeile.partition("=")[2].lstrip().startswith("["), (
            "die Vorlage steht in JSON, die READMEs nennen die Komma-Form"
        )
        monkeypatch.chdir(tmp_path)
        # Nur die Vorlage soll wirken, nicht eine Variable aus der CI-Umgebung.
        for name in ("SWISS_ENERGY_CORS_ORIGINS", "SWISS_ENERGY_ALLOWED_HOSTS"):
            monkeypatch.delenv(name, raising=False)

        s = Settings()

        assert s.cors_origins == ["https://claude.ai"]

    def test_der_deklarierte_boden_traegt_nodecode(self):
        """`NoDecode` ist keine Selbstverstaendlichkeit des Pakets.

        Gemessen, nicht erinnert: in pydantic-settings 2.6.1 gibt es das
        Marker-Objekt nicht, in 2.7.0 schon. Stuende der Boden weiter bei
        2.0.0, waere eine erlaubte Aufloesung eine, in der `settings.py` beim
        Import stirbt — und zwar erst beim Anwender, nie in dieser CI, die
        immer die neueste Version zieht.
        """
        import tomllib
        from importlib.metadata import version as installierte_version

        daten = tomllib.loads((Path(__file__).resolve().parents[1] / "pyproject.toml").read_text())
        specs = [
            d
            for d in daten["project"]["dependencies"]
            if d.split(">=")[0].split("[")[0].strip() == "pydantic-settings"
        ]
        assert len(specs) == 1, f"genau ein Specifier erwartet, gefunden: {specs}"
        boden = specs[0].partition(">=")[2].split(",")[0].strip()
        assert boden, f"kein Untergrenze in {specs[0]!r} — jede alte Version waere erlaubt"

        def teile(v: str) -> tuple[int, ...]:
            return tuple(int(t) for t in v.split(".") if t.isdigit())

        assert teile(boden) >= (2, 7), (
            f"pydantic-settings>={boden} laesst Versionen ohne NoDecode zu"
        )
        # Und die tatsaechlich installierte muss den Boden auch einhalten,
        # sonst prueft der Rest dieser Klasse gegen etwas anderes als deklariert.
        assert teile(installierte_version("pydantic-settings")) >= teile(boden)

    def test_invalid_transport_rejected(self):
        import pydantic

        with pytest.raises(pydantic.ValidationError):
            Settings(_env_file=None, transport="ftp")

    def test_host_default_is_loopback(self):
        assert Settings(_env_file=None).host == "127.0.0.1"
