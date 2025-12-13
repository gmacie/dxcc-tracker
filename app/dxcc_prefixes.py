# app/dxcc_prefixes.py
"""
⚠️ STABLE DXCC ENGINE ⚠️

- Longest-prefix-wins is correct
- Prefix list verified
- KH2 / Guam verified
- Do NOT change matching order
- Do NOT modify without tests

Last verified: 2025-12-13
"""

"""
DXCC prefix resolution engine backed by SQLite reference tables.

- DXCC entities and prefixes live in SQLite
- Loaded once into memory
- Longest-prefix-wins resolution
- Supports active vs deleted entities
- Admin-triggered cache reload supported
"""

from __future__ import annotations
import sqlite3
from typing import Dict, List, Tuple, Optional

from app.config import DB_PATH


# ------------------------------------------------------------
# In-memory cache
# ------------------------------------------------------------

# entity_id -> {"name": str, "active": bool}
DXCC_ENTITIES: Dict[str, Dict[str, object]] = {}

# list of (prefix, entity_id), sorted longest-prefix first
DXCC_PREFIX_RULES: List[Tuple[str, str]] = []

_DXCC_LOADED = False


# ------------------------------------------------------------
# Load DXCC data from SQLite (once)
# ------------------------------------------------------------

def load_dxcc_data(force_reload: bool = False):
    """
    Load DXCC entities and prefixes from SQLite into memory.
    Called once at app startup or manually via admin reload.
    """
    global _DXCC_LOADED

    if _DXCC_LOADED and not force_reload:
        return

    DXCC_ENTITIES.clear()
    DXCC_PREFIX_RULES.clear()

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    # Load entities
    cur.execute("SELECT entity_id, name, active FROM dxcc_entities")
    for entity_id, name, active in cur.fetchall():
        DXCC_ENTITIES[str(entity_id)] = {
            "name": name,
            "active": bool(active),
        }

    # Load prefixes
    cur.execute("SELECT prefix, entity_id FROM dxcc_prefixes")
    for prefix, entity_id in cur.fetchall():
        DXCC_PREFIX_RULES.append((prefix.upper(), str(entity_id)))

    con.close()

    # Longest prefix wins
    DXCC_PREFIX_RULES.sort(key=lambda r: len(r[0]), reverse=True)

    _DXCC_LOADED = True

    print(
        f"DXCC cache loaded: "
        f"{sum(1 for e in DXCC_ENTITIES.values() if e['active'])} active / "
        f"{len(DXCC_ENTITIES)} total"
    )


# ------------------------------------------------------------
# Admin cache reload
# ------------------------------------------------------------

def reload_dxcc_cache():
    """
    Force reload DXCC data from SQLite.
    Intended for admin-only use.
    """
    global _DXCC_LOADED
    _DXCC_LOADED = False
    load_dxcc_data(force_reload=True)


# ------------------------------------------------------------
# Prefix / entity resolution
# ------------------------------------------------------------

def resolve_callsign(call: str) -> Optional[str]:
    """
    Resolve a callsign to a DXCC entity_id using longest-prefix match.
    Returns entity_id or None.
    """
    if not call:
        return None

    call = call.upper()

    for prefix, entity_id in DXCC_PREFIX_RULES:
        if call.startswith(prefix):
            return entity_id

    return None


def entity_for_callsign(call: str) -> Tuple[Optional[str], str, bool]:
    """
    Resolve callsign to:
        (entity_id, entity_name, is_active)

    If no match is found:
        (None, "Unknown", False)
    """
    entity_id = resolve_callsign(call)

    if not entity_id:
        return None, "Unknown", False

    ent = DXCC_ENTITIES.get(entity_id)
    if not ent:
        return entity_id, "Unknown", False

    return entity_id, ent["name"], ent["active"]

def prefix_for_callsign(call: str) -> str | None:
    """
    Return the longest matching DXCC prefix for a callsign.
    """
    if not call:
        return None

    call = call.upper()

    for prefix, _entity_id in DXCC_PREFIX_RULES:
        if call.startswith(prefix):
            return prefix

    return None
