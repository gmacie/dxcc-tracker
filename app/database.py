import os
import sqlite3
import shutil

from app.dxcc_prefixes import entity_for_callsign, DXCC_ENTITIES

# ---- DB PATH ----
# Use the path you currently deploy with. If you're using the Docker
# volume-based setup, this should be "/data/dxcc.db".
# For local-only development you can change this back to a relative path
# like os.path.join(os.path.dirname(__file__), "dxcc.db") if you prefer.

if os.name == "nt":  # Windows dev
    DB_PATH = os.path.join(os.path.dirname(__file__), "dxcc.db")
else:  # Linux / Docker
    DB_PATH = "/data/dxcc.db"



# Optional migration from an older location (e.g., app/dxcc.db or userdata/dxcc.db)
OLD_DB_CANDIDATES = [
    os.path.join(os.path.dirname(__file__), "dxcc.db"),
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "userdata", "dxcc.db"),
]

for old_db in OLD_DB_CANDIDATES:
    try:
        if os.path.exists(old_db) and not os.path.exists(DB_PATH):
            os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
            print(f"Migrating existing DB from {old_db} to {DB_PATH}...")
            shutil.copy(old_db, DB_PATH)
            break
    except Exception as e:
        print(f"DB migration error from {old_db}: {e}")


def resolve_prefix_and_country(call_worked: str, fallback_country: str | None = None):
    """
    Resolve callsign using DXCC prefix engine (LoTW / ARRL standard).
    """
    
    from app import dxcc_prefixes
    
    if not call_worked:
        return None, fallback_country or "Unknown", False
        
    prefix, country, active = dxcc_prefixes.resolve_callsign(call_worked)

    if country:
        return prefix, country, not active  # deleted = not active

    return None, fallback_country or "Unknown", False


# -------------------------------
# Initialize database
# -------------------------------
def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    # Ensure admin column exists
    cur.execute("PRAGMA table_info(users)")
    cols = [c[1] for c in cur.fetchall()]
    if "is_admin" not in cols:
        cur.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0")

    # New schema with prefix + call_worked
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS qsos (
            callsign    TEXT,   -- user callsign (e.g. N4LR)
            country     TEXT,   -- DXCC country name
            prefix      TEXT,   -- DXCC prefix (e.g. ZS1, JA, 4X)
            call_worked TEXT,   -- full callsign worked (e.g. ZS1ABC)
            qso_date    TEXT,
            qsl_status  TEXT,
            band        TEXT
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            callsign TEXT PRIMARY KEY,
            password_hash TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS user_profile (
            callsign        TEXT PRIMARY KEY,
            track_all       INTEGER,
            bands           TEXT,
            include_deleted INTEGER
        )
        """
    )

    con.commit()
    con.close()


# -------------------------------
# QSO Operations
# -------------------------------
def add_qso(user, country, call_worked, date, status, band):
    """
    Insert a new QSO.

    For backward compatibility with existing callers:
      - 'country' is still passed in, but we will override it if
        we can resolve a more accurate country from DXCC prefixes.
    """
    prefix, resolved_country, _deleted = resolve_prefix_and_country(
        call_worked, fallback_country=country
    )
    if resolved_country:
        country = resolved_country

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute(
        """
        INSERT INTO qsos
            (callsign, country, prefix, call_worked, qso_date, qsl_status, band)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (user, country, prefix, call_worked, date, status, band),
    )
    con.commit()
    con.close()


def delete_qso(user, country, call_worked, date, status, band):
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute(
        """
        DELETE FROM qsos
        WHERE callsign = ?
          AND country = ?
          AND call_worked = ?
          AND qso_date = ?
          AND qsl_status = ?
          AND band = ?
        """,
        (user, country, call_worked, date, status, band),
    )
    con.commit()
    con.close()


def update_qso(user, old_row, new_row):
    """
    old_row and new_row are tuples of:
       (country, call_worked, qso_date, qsl_status, band)

    This matches how your UI previously treated:
       (country, qso_call, qso_date, qsl_status, band)
    """
    old_country, old_call_worked, old_date, old_status, old_band = old_row
    new_country, new_call_worked, new_date, new_status, new_band = new_row

    prefix, resolved_country, _deleted = resolve_prefix_and_country(
        new_call_worked, fallback_country=new_country
    )
    if resolved_country:
        new_country = resolved_country

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    cur.execute(
        """
        UPDATE qsos
        SET country = ?, prefix = ?, call_worked = ?, qso_date = ?, qsl_status = ?, band = ?
        WHERE callsign    = ?
          AND country     = ?
          AND call_worked = ?
          AND qso_date    = ?
          AND qsl_status  = ?
          AND band        = ?
        """,
        (
            new_country,
            prefix,
            new_call_worked,
            new_date,
            new_status,
            new_band,
            user,
            old_country,
            old_call_worked,
            old_date,
            old_status,
            old_band,
        ),
    )

    con.commit()
    con.close()

    
def get_qsos_for_user(user):
    """
    Returns rows shaped like:
        (prefix, country, call_worked, qso_date, qsl_status, band)
    """
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute(
        """
        SELECT prefix, country, call_worked, qso_date, qsl_status, band
        FROM qsos
        WHERE callsign = ?
        """,
        (user,),
    )
    rows = cur.fetchall()
    con.close()

    # ---- ASSERTION GUARD ----
    if rows:
        expected_len = 6
        actual_len = len(rows[0])
        assert (
            actual_len == expected_len
        ), f"QSOs schema mismatch: expected {expected_len} columns, got {actual_len}"

    return rows


def qso_exists(user, call_worked, date, band):
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


def update_qso_status(user, call_worked, date, band, new_status):
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute(
        """
        UPDATE qsos
        SET qsl_status = ?
        WHERE callsign = ?
          AND call_worked = ?
          AND qso_date = ?
          AND band = ?
        """,
        (new_status, user, call_worked, date, band),
    )
    con.commit()
    con.close()


# -------------------------------
# User profile operations
# -------------------------------
def get_user_profile(callsign):
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

    if not row:
        # Defaults: track_all = True, no specific bands, don't include deleted
        return True, [], False

    track_all = bool(row[0])
    bands = row[1].split(",") if row[1] else []
    include_deleted = bool(row[2])

    return track_all, bands, include_deleted


def set_user_profile(callsign, track_all, bands, include_deleted):
    band_str = ",".join(bands)

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    cur.execute(
        """
        INSERT INTO user_profile (callsign, track_all, bands, include_deleted)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(callsign) DO UPDATE SET
            track_all       = excluded.track_all,
            bands           = excluded.bands,
            include_deleted = excluded.include_deleted
        """,
        (callsign, int(track_all), band_str, int(include_deleted)),
    )

    con.commit()
    con.close()

def get_dxcc_dashboard(
    
    user: str,
    bands: list[str] | None,
    include_deleted: bool
):
    from app import dxcc_prefixes
    
    """
    Returns:
        worked_entities: set(entity_id)
        confirmed_entities: set(entity_id)
        total_active: int
    """

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    if bands:
        placeholders = ",".join("?" * len(bands))
        cur.execute(
            f"""
            SELECT call_worked, qsl_status, band
            FROM qsos
            WHERE callsign = ?
              AND band IN ({placeholders})
            """,
            (user, *bands),
        )
    else:
        cur.execute(
            """
            SELECT call_worked, qsl_status, band
            FROM qsos
            WHERE callsign = ?
            """,
            (user,),
        )

    rows = cur.fetchall()
    con.close()

    worked = set()
    confirmed = set()

    for call_worked, qsl_status, band in rows:
        eid, _name, active = dxcc_prefixes.entity_for_callsign(call_worked)
        if not eid:
            continue

        if not include_deleted and not active:
            continue

        worked.add(eid)
        if qsl_status in ("Confirmed", "LoTW", "QSL"):
            confirmed.add(eid)

    total_active = sum(
        1 for e in dxcc_prefixes.DXCC_ENTITIES.values() if e["active"]
    )

    return worked, confirmed, total_active
    
# update 12/12/2025 6:33 pm
def get_dxcc_need_list(user, bands, include_deleted):
    """
    Returns a list of (entity_id, country, band)
    where the entity is NOT confirmed on that band.
    """
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    if bands:
        placeholders = ",".join("?" * len(bands))
        cur.execute(
            f"""
            SELECT call_worked, qsl_status, band
            FROM qsos
            WHERE callsign = ?
              AND band IN ({placeholders})
            """,
            (user, *bands),
        )
    else:
        cur.execute(
            """
            SELECT call_worked, qsl_status, band
            FROM qsos
            WHERE callsign = ?
            """,
            (user,),
        )

    rows = cur.fetchall()
    con.close()

    worked = set()
    confirmed = set()

    for call, status, band in rows:
        eid, name, active = entity_for_callsign(call)
        if not eid:
            continue

        if not include_deleted and not active:
            continue

        worked.add((eid, band))
        if status in ("Confirmed", "LoTW", "QSL"):
            confirmed.add((eid, band))

    needs = []

    for eid, ent in DXCC_ENTITIES.items():
        if not include_deleted and not ent.get("active", True):
            continue

        for band in bands:
            if (eid, band) in confirmed:
                continue
            if (eid, band) in worked:
                needs.append((eid, ent.get("name", "Unknown"), band))

    return needs
    
def is_admin_user(callsign: str) -> bool:
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute(
        "SELECT is_admin FROM users WHERE callsign = ?",
        (callsign,),
    )
    row = cur.fetchone()
    con.close()
    return bool(row and row[0])


def get_dxcc_stats():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    cur.execute("SELECT COUNT(*) FROM dxcc_entities")
    total = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM dxcc_entities WHERE active = 1")
    active = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM dxcc_prefixes")
    prefixes = cur.fetchone()[0]

    con.close()
    return active, total, prefixes
    
def backfill_qso_prefixes(dry_run: bool = False):
    """
    One-time migration:
    Populate qsos.prefix using the DXCC prefix engine.

    Safe to re-run.
    """
    from app import dxcc_prefixes

    # REQUIRED for CLI / REPL usage
    dxcc_prefixes.load_dxcc_data()

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    cur.execute(
        """
        SELECT rowid, call_worked, prefix
        FROM qsos
        WHERE prefix IS NULL OR TRIM(prefix) = ''
        """
    )

    rows = cur.fetchall()

    updated = 0
    skipped = 0
    unresolved = 0

    for rowid, call, existing_prefix in rows:
        if not call:
            unresolved += 1
            continue

        # NEW: prefix resolution
        prefix = dxcc_prefixes.prefix_for_callsign(call)

        if not prefix:
            unresolved += 1
            continue

        if dry_run:
            print(f"[DRY RUN] {call} → {prefix}")
            updated += 1
            continue

        cur.execute(
            "UPDATE qsos SET prefix = ? WHERE rowid = ?",
            (prefix, rowid),
        )
        updated += 1

    if not dry_run:
        con.commit()

    con.close()

    print("DXCC prefix backfill complete:")
    print(f"  Updated:    {updated}")
    print(f"  Skipped:    {skipped}")
    print(f"  Unresolved: {unresolved}")
