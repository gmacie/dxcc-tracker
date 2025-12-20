"""
⚠️ ENHANCED DXCC ENGINE WITH CTY PRIMARY ⚠️

Primary: CTY.DAT data (letter prefixes like "K", "VE") from cty_entities/cty_prefixes tables
Fallback: DXCC entities (numeric IDs) from dxcc_entities/dxcc_prefixes tables

This gives comprehensive coverage with user-friendly letter prefixes.
"""

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

# CTY fallback data
CTY_ENTITIES: Dict[str, Dict[str, object]] = {}
CTY_PREFIX_RULES: List[Tuple[str, str, bool]] = []  # (prefix, entity_id, exact_match)

_DXCC_LOADED = False


# ------------------------------------------------------------
# Load DXCC data from SQLite (once)
# ------------------------------------------------------------

def load_dxcc_data(force_reload: bool = False):
    """
    Load DXCC entities and prefixes from SQLite into memory.
    Also loads CTY fallback data.
    Called once at app startup or manually via admin reload.
    """
    global _DXCC_LOADED

    if _DXCC_LOADED and not force_reload:
        return

    DXCC_ENTITIES.clear()
    DXCC_PREFIX_RULES.clear()
    CTY_ENTITIES.clear()
    CTY_PREFIX_RULES.clear()

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    # Load DXCC entities
    cur.execute("SELECT entity_id, name, active FROM dxcc_entities")
    for entity_id, name, active in cur.fetchall():
        DXCC_ENTITIES[str(entity_id)] = {
            "name": name,
            "active": bool(active),
        }

    # Load DXCC prefixes
    cur.execute("SELECT prefix, entity_id FROM dxcc_prefixes")
    for prefix, entity_id in cur.fetchall():
        DXCC_PREFIX_RULES.append((prefix.upper(), str(entity_id)))

    # Load CTY entities (fallback)
    try:
        cur.execute("SELECT entity_id, name, active FROM cty_entities")
        for entity_id, name, active in cur.fetchall():
            CTY_ENTITIES[str(entity_id)] = {
                "name": name,
                "active": bool(active),
            }
    except sqlite3.OperationalError:
        # CTY tables don't exist yet
        pass

    # Load CTY prefixes (fallback)
    try:
        cur.execute("SELECT prefix, entity_id, exact_match FROM cty_prefixes")
        for prefix, entity_id, exact_match in cur.fetchall():
            CTY_PREFIX_RULES.append((prefix.upper(), str(entity_id), bool(exact_match)))
    except sqlite3.OperationalError:
        # CTY tables don't exist yet
        pass

    con.close()

    # Longest prefix wins
    DXCC_PREFIX_RULES.sort(key=lambda r: len(r[0]), reverse=True)
    CTY_PREFIX_RULES.sort(key=lambda r: len(r[0]), reverse=True)

    _DXCC_LOADED = True

    print(
        f"DXCC cache loaded: "
        f"{sum(1 for e in DXCC_ENTITIES.values() if e['active'])} active / "
        f"{len(DXCC_ENTITIES)} total"
    )
    
    if CTY_ENTITIES:
        print(f"CTY fallback loaded: {len(CTY_ENTITIES)} entities, {len(CTY_PREFIX_RULES)} prefixes")


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
# Prefix / entity resolution with CTY fallback
# ------------------------------------------------------------

def resolve_callsign(call: str) -> Optional[str]:
    """
    Resolve a callsign to entity_id using longest-prefix match.
    Tries CTY first (letter prefixes), then falls back to DXCC (numeric IDs).
    Returns entity_id or None.
    """
    if not call:
        return None

    call = call.upper()

    # Try CTY first (gives us letter prefixes like "K", "VE")
    for prefix, entity_id, exact_match in CTY_PREFIX_RULES:
        if exact_match:
            # Exact callsign match
            if call == prefix:
                return entity_id
        else:
            # Prefix match
            if call.startswith(prefix):
                return entity_id

    # Fallback to DXCC (numeric entity IDs)
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

    # Try CTY first (letter prefixes)
    ent = CTY_ENTITIES.get(entity_id)
    if ent:
        return entity_id, ent["name"], ent["active"]
    
    # Fallback to DXCC (numeric IDs)
    ent = DXCC_ENTITIES.get(entity_id)
    if ent:
        return entity_id, ent["name"], ent["active"]

    return entity_id, "Unknown", False


def prefix_for_callsign(call: str) -> str | None:
    """
    Return the longest matching prefix for a callsign.
    Tries CTY first (letter prefixes), then falls back to DXCC.
    """
    if not call:
        return None

    call = call.upper()

    # Try CTY first (letter prefixes)
    for prefix, _entity_id, exact_match in CTY_PREFIX_RULES:
        if exact_match:
            if call == prefix:
                return prefix
        else:
            if call.startswith(prefix):
                return prefix

    # Fallback to DXCC
    for prefix, _entity_id in DXCC_PREFIX_RULES:
        if call.startswith(prefix):
            return prefix

    return None