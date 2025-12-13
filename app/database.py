import os
import sqlite3
import shutil
from datetime import datetime, UTC

from app import dxcc_prefixes
from app.config import DB_PATH


# ------------------------------------------------------------
# Init / migration
# ------------------------------------------------------------

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    # Users
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            callsign TEXT PRIMARY KEY,
            password_hash TEXT,
            is_admin INTEGER DEFAULT 0
        )
    """)

    # QSOs
    cur.execute("""
        CREATE TABLE IF NOT EXISTS qsos (
            callsign TEXT,
            country TEXT,
            prefix TEXT,
            call_worked TEXT,
            qso_date TEXT,
            qsl_status TEXT,
            band TEXT
        )
    """)

    # User profile
    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_profile (
            callsign TEXT PRIMARY KEY,
            track_all INTEGER,
            bands TEXT,
            include_deleted INTEGER
        )
    """)

    # LoTW cache
    cur.execute("""
        CREATE TABLE IF NOT EXISTS lotw_users (
            callsign TEXT PRIMARY KEY,
            last_upload TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS lotw_meta (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    con.commit()
    con.close()


# ------------------------------------------------------------
# QSO helpers
# ------------------------------------------------------------

def add_qso(user, country, call_worked, date, status, band):
    eid, name, active = dxcc_prefixes.entity_for_callsign(call_worked)
    prefix = dxcc_prefixes.prefix_for_callsign(call_worked) or ""

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("""
        INSERT INTO qsos VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        user,
        name,
        prefix,
        call_worked,
        date,
        status,
        band,
    ))
    con.commit()
    con.close()


def delete_qso(user, country, call_worked, date, status, band):
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("""
        DELETE FROM qsos
        WHERE callsign=? AND call_worked=? AND qso_date=? AND band=? AND qsl_status=?
    """, (user, call_worked, date, band, status))
    con.commit()
    con.close()


def get_qsos_for_user(user):
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("""
        SELECT prefix, country, call_worked, qso_date, qsl_status, band
        FROM qsos
        WHERE callsign=?
        ORDER BY band, prefix
    """, (user,))
    rows = cur.fetchall()
    con.close()
    return rows

def qso_exists(user, call_worked, date, band):
    """
    Check if a QSO already exists for a user.
    Used by ADIF import to avoid duplicates.

    Returns:
        qsl_status (str) if exists
        None if not
    """
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    cur.execute(
        """
        SELECT qsl_status
        FROM qsos
        WHERE callsign = ?
          AND call_worked = ?
          AND qso_date = ?
          AND band = ?
        """,
        (user, call_worked, date, band),
    )

    row = cur.fetchone()
    con.close()

    return row[0] if row else None

# ------------------------------------------------------------
# Dashboard logic
# ------------------------------------------------------------

def get_dxcc_dashboard(user, bands, include_deleted):
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    if bands:
        placeholders = ",".join("?" * len(bands))
        cur.execute(f"""
            SELECT call_worked, qsl_status, band
            FROM qsos
            WHERE callsign=? AND band IN ({placeholders})
        """, (user, *bands))
    else:
        cur.execute("""
            SELECT call_worked, qsl_status, band
            FROM qsos
            WHERE callsign=?
        """, (user,))

    rows = cur.fetchall()
    con.close()

    worked = set()
    confirmed = set()

    for call, status, band in rows:
        eid, _, active = dxcc_prefixes.entity_for_callsign(call)
        if not eid:
            continue
        if not include_deleted and not active:
            continue
        worked.add(eid)
        if status in ("Confirmed", "LoTW", "QSL"):
            confirmed.add(eid)

    total_active = sum(
        1 for e in dxcc_prefixes.DXCC_ENTITIES.values() if e["active"]
    )

    return worked, confirmed, total_active


# ------------------------------------------------------------
# DXCC Need List
# ------------------------------------------------------------

def get_dxcc_need_list(user, bands, include_deleted):
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    placeholders = ",".join("?" * len(bands))
    cur.execute(f"""
        SELECT call_worked, qsl_status, band
        FROM qsos
        WHERE callsign=? AND band IN ({placeholders})
    """, (user, *bands))

    rows = cur.fetchall()
    con.close()

    worked = set()
    confirmed = set()

    for call, status, band in rows:
        eid, name, active = dxcc_prefixes.entity_for_callsign(call)
        if not eid:
            continue
        if not include_deleted and not active:
            continue
        worked.add((eid, band))
        if status in ("Confirmed", "LoTW", "QSL"):
            confirmed.add((eid, band))

    needs = []
    for eid, ent in dxcc_prefixes.DXCC_ENTITIES.items():
        if not include_deleted and not ent["active"]:
            continue
        for band in bands:
            if (eid, band) in worked and (eid, band) not in confirmed:
                needs.append((eid, ent["name"], band))

    return needs


# ------------------------------------------------------------
# LoTW lookup
# ------------------------------------------------------------

def get_lotw_last_upload(call):
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("""
        SELECT last_upload FROM lotw_users WHERE callsign=?
    """, (call.upper(),))
    row = cur.fetchone()
    con.close()
    return row[0] if row else None

def get_user_profile(callsign):
    """
    Returns:
        track_all (bool)
        bands (list[str])
        include_deleted (bool)
    """
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    cur.execute(
        """
        SELECT track_all, bands, include_deleted
        FROM user_profile
        WHERE callsign = ?
        """,
        (callsign,),
    )
    row = cur.fetchone()
    con.close()

    # Defaults if no profile exists yet
    if not row:
        return True, [], False

    track_all = bool(row[0])
    bands = row[1].split(",") if row[1] else []
    include_deleted = bool(row[2])

    return track_all, bands, include_deleted


# ------------------------------------------------------------
# Admin helpers
# ------------------------------------------------------------

def is_admin_user(callsign):
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("SELECT is_admin FROM users WHERE callsign=?", (callsign,))
    row = cur.fetchone()
    con.close()
    return bool(row and row[0])


def get_dxcc_stats():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("SELECT COUNT(*) FROM dxcc_entities WHERE active=1")
    active = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM dxcc_entities")
    total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM dxcc_prefixes")
    prefixes = cur.fetchone()[0]
    con.close()
    return active, total, prefixes

def backfill_qso_countries():
    """
    One-time repair:
    Recompute DXCC country name for every QSO based on callsign.
    Updates qsos.country using dxcc_prefixes.entity_for_callsign().
    """
    from app import dxcc_prefixes

    dxcc_prefixes.load_dxcc_data(force_reload=True)

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    cur.execute("SELECT rowid, call_worked, country FROM qsos")
    rows = cur.fetchall()

    updated = 0
    skipped = 0
    unresolved = 0

    for rowid, call, old_country in rows:
        if not call:
            unresolved += 1
            continue

        eid, name, _active = dxcc_prefixes.entity_for_callsign(call)
        if not eid or not name or name == "Unknown":
            unresolved += 1
            continue

        if old_country == name:
            skipped += 1
            continue

        cur.execute("UPDATE qsos SET country=? WHERE rowid=?", (name, rowid))
        updated += 1

    con.commit()
    con.close()

    print(
        "DXCC country backfill complete:\n"
        f"  Updated:    {updated}\n"
        f"  Skipped:    {skipped}\n"
        f"  Unresolved: {unresolved}"
    )
