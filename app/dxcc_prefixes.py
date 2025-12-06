# app/dxcc_prefixes.py

"""
Hybrid DXCC prefix engine.

Design:
- Longest prefix wins (ClubLog-style).
- DXCC_ENTITIES:   entity_id -> {"name": ..., "active": bool}
- DXCC_PREFIX_RULES: ordered list of {"prefix": "KH6", "entity_id": "HAWAII"}

This module ships with a *reasonably complete* built-in prefix map
for common entities, and supports loading a FULL DXCC dataset from
JSON files you maintain locally, e.g.:

    data/dxcc_entities.json
    data/dxcc_prefixes.json

Those JSON files can be generated from:
- ARRL DXCC current/deleted lists
- Open dxcc-json reference (k0swe/dxcc-json on GitHub)
- ClubLog prefix tables (exported for your personal use)
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Dict, List, Tuple
import json
import os


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DXCCEntity:
    id: str         # internal ID, e.g. "USA", "HAWAII", "JA"
    name: str       # human readable name, e.g. "United States"
    active: bool    # True = current DXCC, False = deleted


@dataclass(frozen=True)
class PrefixRule:
    prefix: str     # e.g. "KH6", "KL7", "JA"
    entity_id: str  # key into DXCC_ENTITIES


# ---------------------------------------------------------------------------
# Built-in entities (partial – common ones + template)
# You can extend this or override entirely from JSON.
# ---------------------------------------------------------------------------

DXCC_ENTITIES: Dict[str, DXCCEntity] = {
    # --- North America (examples) ---
    "USA": DXCCEntity("USA", "United States", True),
    "ALASKA": DXCCEntity("ALASKA", "Alaska", True),
    "HAWAII": DXCCEntity("HAWAII", "Hawaii", True),
    "PUERTO_RICO": DXCCEntity("PUERTO_RICO", "Puerto Rico", True),
    "US_VIRGIN": DXCCEntity("US_VIRGIN", "US Virgin Islands", True),
    "GUANTANAMO": DXCCEntity("GUANTANAMO", "Guantanamo Bay", True),

    "CANADA": DXCCEntity("CANADA", "Canada", True),
    "MEXICO": DXCCEntity("MEXICO", "Mexico", True),
    "BERMUDA": DXCCEntity("BERMUDA", "Bermuda", True),
    "GREENLAND": DXCCEntity("GREENLAND", "Greenland", True),
    "ST_PIERRE_MIQUELON": DXCCEntity("SPM", "St Pierre & Miquelon", True),
    "CAYMAN": DXCCEntity("CAYMAN", "Cayman Islands", True),
    "BAHAMAS": DXCCEntity("BAHAMAS", "Bahamas", True),
    "BARBADOS": DXCCEntity("BARBADOS", "Barbados", True),
    "TURKS_CAICOS": DXCCEntity("TURKS_CAICOS", "Turks & Caicos", True),

    # --- Europe (examples) ---
    "ENGLAND": DXCCEntity("ENGLAND", "England", True),
    "SCOTLAND": DXCCEntity("SCOTLAND", "Scotland", True),
    "WALES": DXCCEntity("WALES", "Wales", True),
    "N_IRELAND": DXCCEntity("N_IRELAND", "Northern Ireland", True),
    "ISLE_OF_MAN": DXCCEntity("ISLE_OF_MAN", "Isle of Man", True),
    "GUERNSEY": DXCCEntity("GUERNSEY", "Guernsey", True),
    "JERSEY": DXCCEntity("JERSEY", "Jersey", True),

    "FRANCE": DXCCEntity("FRANCE", "France", True),
    "CORSICA": DXCCEntity("CORSICA", "Corsica", True),
    "MONACO": DXCCEntity("MONACO", "Monaco", True),
    "SPAIN": DXCCEntity("SPAIN", "Spain", True),
    "PORTUGAL": DXCCEntity("PORTUGAL", "Portugal", True),
    "ITALY": DXCCEntity("ITALY", "Italy", True),
    "SARDINIA": DXCCEntity("SARDINIA", "Sardinia", True),
    "SICILY": DXCCEntity("SICILY", "Sicily", True),

    "GERMANY": DXCCEntity("GERMANY", "Germany", True),
    "AUSTRIA": DXCCEntity("AUSTRIA", "Austria", True),
    "SWITZERLAND": DXCCEntity("SWITZERLAND", "Switzerland", True),
    "BELGIUM": DXCCEntity("BELGIUM", "Belgium", True),
    "NETHERLANDS": DXCCEntity("NETHERLANDS", "Netherlands", True),
    "LUXEMBOURG": DXCCEntity("LUXEMBOURG", "Luxembourg", True),
    "DENMARK": DXCCEntity("DENMARK", "Denmark", True),
    "NORWAY": DXCCEntity("NORWAY", "Norway", True),
    "SWEDEN": DXCCEntity("SWEDEN", "Sweden", True),
    "FINLAND": DXCCEntity("FINLAND", "Finland", True),

    "POLAND": DXCCEntity("POLAND", "Poland", True),
    "CZECH": DXCCEntity("CZECH", "Czech Republic", True),
    "SLOVAKIA": DXCCEntity("SLOVAKIA", "Slovakia", True),
    "HUNGARY": DXCCEntity("HUNGARY", "Hungary", True),
    "ROMANIA": DXCCEntity("ROMANIA", "Romania", True),
    "BULGARIA": DXCCEntity("BULGARIA", "Bulgaria", True),
    "UKRAINE": DXCCEntity("UKRAINE", "Ukraine", True),
    "RUSSIA_EU": DXCCEntity("RUSSIA_EU", "European Russia", True),
    "RUSSIA_AS": DXCCEntity("RUSSIA_AS", "Asiatic Russia", True),

    # --- Asia (examples) ---
    "JAPAN": DXCCEntity("JAPAN", "Japan", True),
    "KOREA_S": DXCCEntity("KOREA_S", "South Korea", True),
    "CHINA": DXCCEntity("CHINA", "China", True),
    "TAIWAN": DXCCEntity("TAIWAN", "Taiwan", True),
    "HONG_KONG": DXCCEntity("HONG_KONG", "Hong Kong", True),
    "MACAU": DXCCEntity("MACAU", "Macau", True),
    "PHILIPPINES": DXCCEntity("PHILIPPINES", "Philippines", True),
    "THAILAND": DXCCEntity("THAILAND", "Thailand", True),
    "VIETNAM": DXCCEntity("VIETNAM", "Vietnam", True),
    "CAMBODIA": DXCCEntity("CAMBODIA", "Cambodia", True),
    "LAOS": DXCCEntity("LAOS", "Laos", True),
    "MALAYSIA_W": DXCCEntity("MALAYSIA_W", "West Malaysia", True),
    "MALAYSIA_E": DXCCEntity("MALAYSIA_E", "East Malaysia", True),
    "SINGAPORE": DXCCEntity("SINGAPORE", "Singapore", True),
    "INDIA": DXCCEntity("INDIA", "India", True),
    "SRI_LANKA": DXCCEntity("SRI_LANKA", "Sri Lanka", True),

    # --- Oceania (examples) ---
    "VK_MAIN": DXCCEntity("VK_MAIN", "Australia", True),
    "VK0_HEARD": DXCCEntity("VK0_HEARD", "Heard Island", True),
    "VK0_MACQ": DXCCEntity("VK0_MACQ", "Macquarie Island", True),
    "VK9_NORFOLK": DXCCEntity("VK9_NORFOLK", "Norfolk Island", True),
    "VK9_LORD_HOWE": DXCCEntity("VK9_LORD_HOWE", "Lord Howe Island", True),
    "VK9_CHRISTMAS": DXCCEntity("VK9_CHRISTMAS", "Christmas Island", True),
    "VK9_COCOS": DXCCEntity("VK9_COCOS", "Cocos (Keeling) Islands", True),

    "ZL_MAIN": DXCCEntity("ZL_MAIN", "New Zealand", True),
    "ZL7_CHATHAM": DXCCEntity("ZL7_CHATHAM", "Chatham Islands", True),
    "ZL8_KERMADEC": DXCCEntity("ZL8_KERMADEC", "Kermadec Islands", True),
    "ZL9_AUCKLAND": DXCCEntity("ZL9_AUCKLAND", "Auckland & Campbell Islands", True),

    "FIJI": DXCCEntity("FIJI", "Fiji", True),
    "AMERICAN_SAMOA": DXCCEntity("AMERICAN_SAMOA", "American Samoa", True),
    "SAMOA": DXCCEntity("SAMOA", "Samoa", True),
    "TONGA": DXCCEntity("TONGA", "Tonga", True),
    "COOK_N": DXCCEntity("COOK_N", "North Cook Islands", True),
    "COOK_S": DXCCEntity("COOK_S", "South Cook Islands", True),

    # --- Africa (examples) ---
    "SOUTH_AFRICA": DXCCEntity("SOUTH_AFRICA", "South Africa", True),
    "NAMIBIA": DXCCEntity("NAMIBIA", "Namibia", True),
    "BOTSWANA": DXCCEntity("BOTSWANA", "Botswana", True),
    "ZIMBABWE": DXCCEntity("ZIMBABWE", "Zimbabwe", True),
    "ANGOLA": DXCCEntity("ANGOLA", "Angola", True),
    "KENYA": DXCCEntity("KENYA", "Kenya", True),
    "TANZANIA": DXCCEntity("TANZANIA", "Tanzania", True),
    "ETHIOPIA": DXCCEntity("ETHIOPIA", "Ethiopia", True),
    "MADAGASCAR": DXCCEntity("MADAGASCAR", "Madagascar", True),

    # --- Latin America / Caribbean (examples) ---
    "ARGENTINA": DXCCEntity("ARGENTINA", "Argentina", True),
    "BRAZIL": DXCCEntity("BRAZIL", "Brazil", True),
    "CHILE": DXCCEntity("CHILE", "Chile", True),
    "URUGUAY": DXCCEntity("URUGUAY", "Uruguay", True),
    "PARAGUAY": DXCCEntity("PARAGUAY", "Paraguay", True),
    "PERU": DXCCEntity("PERU", "Peru", True),
    "COLOMBIA": DXCCEntity("COLOMBIA", "Colombia", True),
    "ECUADOR": DXCCEntity("ECUADOR", "Ecuador", True),
    "GALAPAGOS": DXCCEntity("GALAPAGOS", "Galapagos Islands", True),

    "HONDURAS": DXCCEntity("HONDURAS", "Honduras", True),
    "GUATEMALA": DXCCEntity("GUATEMALA", "Guatemala", True),
    "EL_SALVADOR": DXCCEntity("EL_SALVADOR", "El Salvador", True),
    "NICARAGUA": DXCCEntity("NICARAGUA", "Nicaragua", True),
    "COSTA_RICA": DXCCEntity("COSTA_RICA", "Costa Rica", True),
    "PANAMA": DXCCEntity("PANAMA", "Panama", True),
    "CUBA": DXCCEntity("CUBA", "Cuba", True),
    "DOMINICAN": DXCCEntity("DOMINICAN", "Dominican Republic", True),
    "HAITI": DXCCEntity("HAITI", "Haiti", True),

    # --- Deleted entities examples (set active=False) ---
    "E_GERMANY": DXCCEntity("E_GERMANY", "East Germany", False),
    "W_GERMANY": DXCCEntity("W_GERMANY", "West Germany", False),
    "CZECHOSLOVAKIA": DXCCEntity("CZECHOSLOVAKIA", "Czechoslovakia", False),
    "YUGOSLAVIA": DXCCEntity("YUGOSLAVIA", "Yugoslavia", False),
    "USSR": DXCCEntity("USSR", "USSR", False),
    "CANAL_ZONE": DXCCEntity("CANAL_ZONE", "Panama Canal Zone", False),
    "RHODESIA": DXCCEntity("RHODESIA", "Southern Rhodesia", False),
    "SAAR": DXCCEntity("SAAR", "Saar", False),
    # ... extend with all 62 deleted entities as you build it up ...
}

# ---------------------------------------------------------------------------
# Built-in prefix rules (HYBRID, compact, longest-prefix-wins)
# This is a STARTER SET. You can override/extend via JSON.
# ---------------------------------------------------------------------------

BUILTIN_PREFIX_RULES: List[PrefixRule] = [
    # --- US + possessions ---
    PrefixRule("KH6", "HAWAII"),
    PrefixRule("KH7", "HAWAII"),
    PrefixRule("KL7", "ALASKA"),
    PrefixRule("AL7", "ALASKA"),
    PrefixRule("NL7", "ALASKA"),
    PrefixRule("WL7", "ALASKA"),

    PrefixRule("KP4", "PUERTO_RICO"),
    PrefixRule("NP4", "PUERTO_RICO"),
    PrefixRule("WP4", "PUERTO_RICO"),

    PrefixRule("KP2", "US_VIRGIN"),
    PrefixRule("NP2", "US_VIRGIN"),
    PrefixRule("WP2", "US_VIRGIN"),

    PrefixRule("KG4", "GUANTANAMO"),

    # Base USA
    PrefixRule("AA", "USA"),
    PrefixRule("AB", "USA"),
    PrefixRule("AC", "USA"),
    PrefixRule("AD", "USA"),
    PrefixRule("AE", "USA"),
    PrefixRule("AF", "USA"),
    PrefixRule("AG", "USA"),
    PrefixRule("AJ", "USA"),
    PrefixRule("AK", "USA"),
    PrefixRule("K", "USA"),
    PrefixRule("N", "USA"),
    PrefixRule("W", "USA"),

    # Canada
    PrefixRule("VO1", "CANADA"),   # Newfoundland & Labrador (simplified)
    PrefixRule("VO2", "CANADA"),
    PrefixRule("VY0", "CANADA"),
    PrefixRule("VY1", "CANADA"),
    PrefixRule("VY2", "CANADA"),
    PrefixRule("VA", "CANADA"),
    PrefixRule("VE", "CANADA"),
    PrefixRule("VO", "CANADA"),
    PrefixRule("VY", "CANADA"),

    # Mexico
    PrefixRule("XE", "MEXICO"),
    PrefixRule("XF", "MEXICO"),

    # Bermuda
    PrefixRule("VP9", "BERMUDA"),

    # Caribbean (a few examples)
    PrefixRule("ZF", "CAYMAN"),
    PrefixRule("C6A", "BAHAMAS"),
    PrefixRule("8P", "BARBADOS"),
    PrefixRule("VP5", "TURKS_CAICOS"),

    # UK & dependencies
    PrefixRule("GM", "SCOTLAND"),
    PrefixRule("GS", "SCOTLAND"),
    PrefixRule("GW", "WALES"),
    PrefixRule("GN", "N_IRELAND"),
    PrefixRule("GI", "N_IRELAND"),
    PrefixRule("GD", "ISLE_OF_MAN"),
    PrefixRule("GU", "GUERNSEY"),
    PrefixRule("GP", "GUERNSEY"),
    PrefixRule("GJ", "JERSEY"),
    PrefixRule("GH", "JERSEY"),
    PrefixRule("G", "ENGLAND"),

    # France + Corsica
    PrefixRule("TK", "CORSICA"),
    PrefixRule("F", "FRANCE"),

    # Iberia
    PrefixRule("EA8", "SPAIN"),  # Canary simplified to Spain or separate if you wish
    PrefixRule("EA9", "SPAIN"),  # Ceuta/Melilla
    PrefixRule("EA", "SPAIN"),
    PrefixRule("CT", "PORTUGAL"),
    PrefixRule("CT3", "MADEIRA") if "MADEIRA" in DXCC_ENTITIES else None,
    # Italy + islands
    PrefixRule("IS0", "SARDINIA"),
    PrefixRule("IT9", "SICILY"),
    PrefixRule("I", "ITALY"),

    # Central Europe
    PrefixRule("DL", "GERMANY"),
    PrefixRule("OE", "AUSTRIA"),
    PrefixRule("HB", "SWITZERLAND"),
    PrefixRule("ON", "BELGIUM"),
    PrefixRule("PA", "NETHERLANDS"),
    PrefixRule("LX", "LUXEMBOURG"),
    PrefixRule("OZ", "DENMARK"),
    PrefixRule("LA", "NORWAY"),
    PrefixRule("LN", "NORWAY"),
    PrefixRule("SM", "SWEDEN"),
    PrefixRule("OH", "FINLAND"),

    PrefixRule("SP", "POLAND"),
    PrefixRule("OK", "CZECH"),
    PrefixRule("OL", "CZECH"),
    PrefixRule("OM", "SLOVAKIA"),
    PrefixRule("HA", "HUNGARY"),
    PrefixRule("YO", "ROMANIA"),
    PrefixRule("LZ", "BULGARIA"),
    PrefixRule("UR", "UKRAINE"),
    PrefixRule("UX", "UKRAINE"),

    # Russia (very simplified split)
    PrefixRule("UA0", "RUSSIA_AS"),
    PrefixRule("RA0", "RUSSIA_AS"),
    PrefixRule("R0", "RUSSIA_AS"),
    PrefixRule("UA", "RUSSIA_EU"),
    PrefixRule("RA", "RUSSIA_EU"),
    PrefixRule("R", "RUSSIA_EU"),

    # Japan
    PrefixRule("JA", "JAPAN"),
    PrefixRule("JE", "JAPAN"),
    PrefixRule("JF", "JAPAN"),
    PrefixRule("JG", "JAPAN"),
    PrefixRule("JH", "JAPAN"),
    PrefixRule("JI", "JAPAN"),
    PrefixRule("JJ", "JAPAN"),
    PrefixRule("JK", "JAPAN"),
    PrefixRule("JL", "JAPAN"),
    PrefixRule("JM", "JAPAN"),
    PrefixRule("JN", "JAPAN"),
    PrefixRule("JO", "JAPAN"),

    # Korea, China, SE Asia
    PrefixRule("HL", "KOREA_S"),
    PrefixRule("DS", "KOREA_S"),
    PrefixRule("DT", "KOREA_S"),

    PrefixRule("BY", "CHINA"),
    PrefixRule("BA", "CHINA"),
    PrefixRule("BD", "CHINA"),
    PrefixRule("BG", "CHINA"),
    PrefixRule("BH", "CHINA"),
    PrefixRule("BI", "CHINA"),
    PrefixRule("B", "CHINA"),

    PrefixRule("BV", "TAIWAN"),
    PrefixRule("VR", "HONG_KONG"),
    PrefixRule("XX9", "MACAU"),

    PrefixRule("DU", "PHILIPPINES"),
    PrefixRule("4I", "PHILIPPINES"),

    PrefixRule("HS", "THAILAND"),
    PrefixRule("E2", "THAILAND"),

    PrefixRule("3W", "VIETNAM"),
    PrefixRule("XV", "VIETNAM"),

    PrefixRule("XU", "CAMBODIA"),
    PrefixRule("XW", "LAOS"),

    PrefixRule("9M2", "MALAYSIA_W"),
    PrefixRule("9M4", "MALAYSIA_W"),
    PrefixRule("9M6", "MALAYSIA_E"),
    PrefixRule("9M8", "MALAYSIA_E"),

    PrefixRule("9V", "SINGAPORE"),

    PrefixRule("VU", "INDIA"),
    PrefixRule("VU2", "INDIA"),
    PrefixRule("VU3", "INDIA"),
    PrefixRule("4S", "SRI_LANKA"),

    # VK / ZL examples
    PrefixRule("VK0H", "VK0_HEARD"),
    PrefixRule("VK0M", "VK0_MACQ"),
    PrefixRule("VK9X", "VK9_CHRISTMAS"),
    PrefixRule("VK9C", "VK9_COCOS"),
    PrefixRule("VK9L", "VK9_LORD_HOWE"),
    PrefixRule("VK9N", "VK9_NORFOLK"),
    PrefixRule("VK", "VK_MAIN"),

    PrefixRule("ZL7", "ZL7_CHATHAM"),
    PrefixRule("ZL8", "ZL8_KERMADEC"),
    PrefixRule("ZL9", "ZL9_AUCKLAND"),
    PrefixRule("ZL", "ZL_MAIN"),

    # Pacific islands examples
    PrefixRule("3D2", "FIJI"),
    PrefixRule("KH8", "AMERICAN_SAMOA"),
    PrefixRule("5W", "SAMOA"),
    PrefixRule("A3", "TONGA"),
    # ... add E5/N, E5/S, H40, etc ...

    # Africa a few examples
    PrefixRule("ZS", "SOUTH_AFRICA"),
    PrefixRule("V5", "NAMIBIA"),
    PrefixRule("A2", "BOTSWANA"),
    PrefixRule("Z2", "ZIMBABWE"),
    PrefixRule("D2", "ANGOLA"),
    PrefixRule("5Z", "KENYA"),
    PrefixRule("5H", "TANZANIA"),
    PrefixRule("ET", "ETHIOPIA"),
    PrefixRule("5R", "MADAGASCAR"),

    # Latin America examples
    PrefixRule("LU", "ARGENTINA"),
    PrefixRule("LW", "ARGENTINA"),
    PrefixRule("PP", "BRAZIL"),
    PrefixRule("PQ", "BRAZIL"),
    PrefixRule("PR", "BRAZIL"),
    PrefixRule("PS", "BRAZIL"),
    PrefixRule("PT", "BRAZIL"),
    PrefixRule("PU", "BRAZIL"),

    PrefixRule("CE", "CHILE"),
    PrefixRule("CE0Y", "GALAPAGOS"),
    PrefixRule("HC", "ECUADOR"),
    PrefixRule("HC8", "GALAPAGOS"),

    PrefixRule("HK", "COLOMBIA"),
    PrefixRule("OA", "PERU"),
    PrefixRule("OA0", "PERU"),  # example

    PrefixRule("TG", "GUATEMALA"),
    PrefixRule("HR", "HONDURAS"),
    PrefixRule("YS", "EL_SALVADOR"),
    PrefixRule("YN", "NICARAGUA"),
    PrefixRule("TI", "COSTA_RICA"),
    PrefixRule("HP", "PANAMA"),
    PrefixRule("CM", "CUBA"),
    PrefixRule("CO", "CUBA"),
    PrefixRule("T4", "CUBA"),
    PrefixRule("HI", "DOMINICAN"),
    PrefixRule("HH", "HAITI"),

    # Deleted examples
    PrefixRule("Y2", "E_GERMANY"),
    PrefixRule("DM", "E_GERMANY"),
    PrefixRule("DA1", "E_GERMANY"),   # historical
    PrefixRule("DL2", "W_GERMANY"),   # example only; refine as needed
    PrefixRule("OK3", "CZECHOSLOVAKIA"),
    PrefixRule("OM8", "CZECHOSLOVAKIA"),
    PrefixRule("YU", "YUGOSLAVIA"),
    PrefixRule("UC", "USSR"),
    PrefixRule("UA3", "USSR"),

    # Sentinel (filter out None rules created conditionally)
]

DXCC_PREFIX_RULES: List[PrefixRule] = [r for r in BUILTIN_PREFIX_RULES if r is not None]


# ---------------------------------------------------------------------------
# Optional: load extended data from JSON files (DXCC_ENTITIES & PREFIX_RULES)
# ---------------------------------------------------------------------------

def _load_json_if_exists(path: str):
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_extended_data(base_dir: str = "data"):
    """
    If present, load and merge:
      base_dir/dxcc_entities.json
      base_dir/dxcc_prefixes.json

    JSON formats:

    dxcc_entities.json:
      [
        {"id": "HAWAII", "name": "Hawaii", "active": true},
        ...
      ]

    dxcc_prefixes.json:
      [
        {"prefix": "KH6", "entity_id": "HAWAII"},
        ...
      ]
    """
    global DXCC_ENTITIES, DXCC_PREFIX_RULES

    entities_path = os.path.join(base_dir, "dxcc_entities.json")
    prefixes_path = os.path.join(base_dir, "dxcc_prefixes.json")

    entities_data = _load_json_if_exists(entities_path)
    if entities_data:
        new_entities: Dict[str, DXCCEntity] = {}
        for e in entities_data:
            new_entities[e["id"]] = DXCCEntity(
                id=e["id"],
                name=e["name"],
                active=bool(e.get("active", True)),
            )
        DXCC_ENTITIES = new_entities

    prefixes_data = _load_json_if_exists(prefixes_path)
    if prefixes_data:
        rules: List[PrefixRule] = []
        for r in prefixes_data:
            rules.append(PrefixRule(prefix=r["prefix"].upper(), entity_id=r["entity_id"]))
        # Sort by descending prefix length (longest prefix wins)
        rules.sort(key=lambda pr: len(pr.prefix), reverse=True)
        DXCC_PREFIX_RULES = rules


# ---------------------------------------------------------------------------
# Lookup helpers
# ---------------------------------------------------------------------------

def normalize_call(call: str) -> str:
    return (call or "").strip().upper()


def lookup_entity_id_from_call(call: str) -> Optional[str]:
    """
    Longest-prefix-wins match against DXCC_PREFIX_RULES.
    """
    c = normalize_call(call)
    if not c:
        return None

    for rule in DXCC_PREFIX_RULES:
        if c.startswith(rule.prefix):
            return rule.entity_id
    return None


def lookup_entity_from_call(call: str) -> Optional[Tuple[DXCCEntity, str]]:
    """
    Return (DXCCEntity, entity_name) or None if unknown.
    """
    eid = lookup_entity_id_from_call(call)
    if not eid:
        return None
    ent = DXCC_ENTITIES.get(eid)
    if ent is None:
        return None
    return ent, ent.name


def is_deleted_entity(entity_id: str) -> bool:
    ent = DXCC_ENTITIES.get(entity_id)
    return bool(ent and not ent.active)
