"""Markdown formatting helpers for human-readable tool summaries."""

from __future__ import annotations

import re
from typing import Any

_TURBINE_RE = {
    "mfr": re.compile(r"<tur_manufacturer>(.*?)</tur_manufacturer>"),
    "model": re.compile(r"<tur_model>(.*?)</tur_model>"),
    "hub": re.compile(r"<tur_hubheight>(.*?)</tur_hubheight>"),
}


def format_power_value(value: Any, unit: str = "kW") -> str:
    """Format a power value, converting kW to MW above 1000 kW."""
    if value is None or value == "":
        return "k.A."
    try:
        val = float(str(value).replace(",", "."))
    except (ValueError, TypeError):
        return str(value)
    if unit == "kW" and val >= 1000:
        return f"{val / 1000:.2f} MW"
    return f"{val:.2f} {unit}"


def format_year(value: Any) -> str:
    """Format a year value."""
    if value is None or value == "":
        return "k.A."
    return str(int(value)) if str(value).isdigit() else str(value)


def clean_label(raw: str) -> str:
    """Strip GeoAdmin <b> tags from a label."""
    return raw.replace("<b>", "").replace("</b>", "").strip()


def _attrs(features: list[dict]) -> list[dict]:
    return [f.get("attributes", {}) for f in features]


def format_power_plants(features: list[dict], title: str) -> str:
    """Build the Markdown summary for electricity-production plants."""
    lines = [f"## {title}", f"\n**{len(features)} Anlage(n) gefunden**\n"]
    for attrs in _attrs(features):
        subcat = attrs.get("sub_category_de", "Unbekannt")
        lines.append(f"### {subcat} – {attrs.get('address', 'k.A.')}")
        if attrs.get("canton"):
            lines.append(f"- **Kanton:** {attrs['canton']}")
        lines.append(f"- **Inbetriebnahme:** {attrs.get('beginning_of_operation', 'k.A.')}")
        lines.append(f"- **Anfangsleistung:** {format_power_value(attrs.get('initial_power', ''))}")
        lines.append(f"- **Aktuelle Leistung:** {format_power_value(attrs.get('total_power', ''))}")
        lines.append("")
    return "\n".join(lines)


def format_wind_turbines(features: list[dict], title: str) -> str:
    """Build the Markdown summary for wind turbines."""
    lines = [f"## {title}", f"\n**{len(features)} Anlage(n) gefunden**\n"]
    for attrs in _attrs(features):
        name = attrs.get("fac_name", "Unbekannt")
        fac_type = attrs.get("fac_type_de", "k.A.")
        lines.append(f"### {name} ({fac_type})")
        lines.append(f"- **Betreiber:** {attrs.get('fac_operator', 'k.A.')}")
        lines.append(f"- **Leistung:** {format_power_value(attrs.get('fac_power', ''))}")
        turbine = _turbine_info(attrs.get("turbines", ""))
        if turbine:
            lines.append(f"- **Turbine:** {turbine}")
        if attrs.get("fac_website"):
            lines.append(f"- **Website:** {attrs['fac_website']}")
        lines.append("")
    return "\n".join(lines)


def _turbine_info(turbines_xml: str) -> str:
    if "<tur_manufacturer>" not in turbines_xml:
        return ""
    mfr = _TURBINE_RE["mfr"].search(turbines_xml)
    model = _TURBINE_RE["model"].search(turbines_xml)
    hub = _TURBINE_RE["hub"].search(turbines_xml)
    parts = ""
    if mfr:
        parts = mfr.group(1)
    if model:
        parts += f" {model.group(1)}"
    if hub:
        parts += f" (Nabenhöhe: {hub.group(1)} m)"
    return parts.strip()


def format_hydro_plants(features: list[dict], title: str) -> str:
    """Build the Markdown summary for hydropower plants."""
    lines = [f"## {title}", f"\n**{len(features)} Werk(e) gefunden**\n"]
    for attrs in _attrs(features):
        canton = attrs.get("canton", "")
        lines.append(f"### {attrs.get('name', 'Unbekannt')}")
        lines.append(
            f"- **Standort:** {attrs.get('location', 'k.A.')}{f', {canton}' if canton else ''}"
        )
        lines.append(f"- **Typ:** {attrs.get('hydropowerplanttype_de', 'k.A.')}")
        lines.append(f"- **Status:** {attrs.get('hydropowerplantoperationalstatus_de', 'k.A.')}")
        lines.append(f"- **Inbetriebnahme:** {format_year(attrs.get('beginningofoperation'))}")
        lines.append(
            f"- **Turbinenleistung:** "
            f"{format_power_value(attrs.get('performanceturbinemaximum', ''), 'MW')}"
        )
        lines.append(
            f"- **Erwartete Jahresproduktion:** {attrs.get('productionexpected', 'k.A.')} GWh"
        )
        lines.append("")
    return "\n".join(lines)


def format_pv_plants(features: list[dict], title: str) -> str:
    """Build the Markdown summary for large PV installations."""
    lines = [f"## {title}", f"\n**{len(features)} Anlage(n) gefunden**\n"]
    for attrs in _attrs(features):
        lines.append(f"### {attrs.get('projectname', 'Unbekannt')}")
        lines.append(f"- **Projektleitung:** {attrs.get('projectmanagement', 'k.A.')}")
        lines.append(f"- **Status:** {attrs.get('statuscategory_de', 'k.A.')}")
        if attrs.get("power", "k.A.") != "k.A.":
            lines.append(f"- **Leistung:** {attrs['power']} MWp")
        if attrs.get("annualproduction", "k.A.") != "k.A.":
            lines.append(f"- **Jahresproduktion:** {attrs['annualproduction']} GWh")
        if attrs.get("winterproduction", "k.A.") != "k.A.":
            lines.append(f"- **Winterproduktion:** {attrs['winterproduction']} GWh")
        if attrs.get("projectweb"):
            lines.append(f"- **Website:** {attrs['projectweb']}")
        lines.append("")
    return "\n".join(lines)


def format_biogas_plants(features: list[dict], title: str) -> str:
    """Build the Markdown summary for biogas plants."""
    lines = [f"## {title}", f"\n**{len(features)} Anlage(n) gefunden**\n"]
    for attrs in _attrs(features):
        label = attrs.get("label", attrs.get("name", "Unbekannt"))
        lines.append(f"- **{clean_label(str(label))}**")
        for key, val in attrs.items():
            if key not in ("label", "name") and val and val != "k.A.":
                lines.append(f"  - {key}: {val}")
    return "\n".join(lines)


def format_energy_cities(features: list[dict], title: str) -> str:
    """Build the Markdown summary for 'Energiestadt' municipalities."""
    lines = [f"## {title}", f"\n**{len(features)} Gemeinde(n) gefunden**\n"]
    for attrs in _attrs(features):
        since = str(attrs.get("energiestadtseit", "k.A."))[:4]
        residents = attrs.get("einwohner", "k.A.")
        if residents not in ("k.A.", None, ""):
            try:
                residents = f"{int(residents):,}".replace(",", "'")
            except (ValueError, TypeError):
                pass
        lines.append(f"### {attrs.get('name', 'Unbekannt')}")
        lines.append(f"- **Energiestadt seit:** {since}")
        lines.append(f"- **Punktezahl:** {attrs.get('punktezahl', 'k.A.')}%")
        lines.append(f"- **Einwohner:** {residents}")
        lines.append(f"- **Anzahl Audits:** {attrs.get('anzahlaudits', 'k.A.')}")
        if attrs.get("linkenergiestadtweb"):
            lines.append(f"- **Link:** {attrs['linkenergiestadtweb']}")
        lines.append("")
    return "\n".join(lines)
