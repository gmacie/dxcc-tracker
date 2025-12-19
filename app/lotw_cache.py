from __future__ import annotations

import sqlite3
import requests
from datetime import datetime, UTC, timedelta

from app.config import DB_PATH

LOTW_URL = "https://lotw.arrl.org/lotw-user-activity.csv"
CACHE_TTL = timedelta(days=1)


# ------------------------------------------------------------
# DB setup
# ------------------------------------------------------------

def _init_tables():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS lotw_users (
            callsign TEXT PRIMARY KEY,
            last_upload TEXT
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS lotw_meta (
            key TEXT PRIMARY KEY,
            value TEXT
        )
        """
    )

    con.commit()
    con.close()


def _get_last_refresh():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("SELECT value FROM lotw_meta WHERE key='last_refresh'")
    row = cur.fetchone()
    con.close()
    return datetime.fromisoformat(row[0]) if row else None


def _set_last_refresh(ts):
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute(
        """
        INSERT INTO lotw_meta (key, value)
        VALUES ('last_refresh', ?)
        ON CONFLICT(key) DO UPDATE SET value=excluded.value
        """,
        (ts.isoformat(),),
    )
    con.commit()
    con.close()


# ------------------------------------------------------------
# Public API
# ------------------------------------------------------------

def refresh_lotw_cache(force=False):
    _init_tables()

    now = datetime.now(UTC)
    last = _get_last_refresh()

    if not force and last and now - last < CACHE_TTL:
        return

    print("Refreshing LoTW upload cache...")

    try:
        r = requests.get(
            LOTW_URL,
            timeout=30,
            headers={"User-Agent": "DXCC-Tracker"},
        )
        r.raise_for_status()
        text = r.text.strip()
    except Exception as e:
        print(f"LoTW fetch failed: {e}")
        return

    # Guard: HTML response (common failure mode)
    if text.lower().startswith("<!doctype") or "<html" in text.lower():
        print("LoTW returned HTML instead of CSV — aborting")
        return

    lines = text.splitlines()
    rows = []

    # Detect delimiter
    delimiter = ";" if ";" in lines[0] else ","

    for line in lines[1:]:
        parts = [p.strip() for p in line.split(delimiter)]
        if len(parts) < 2:
            continue

        call = parts[0].upper()
        date = parts[1]

        if call and date:
            rows.append((call, date))

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("DELETE FROM lotw_users")

    cur.executemany(
        "INSERT OR REPLACE INTO lotw_users (callsign, last_upload) VALUES (?, ?)",
        rows,
    )

    con.commit()
    con.close()

    _set_last_refresh(now)

    print(f"LoTW cache refreshed: {len(rows)} callsigns")


def get_lotw_last_upload(callsign):
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute(
        "SELECT last_upload FROM lotw_users WHERE callsign=?",
        (callsign.upper(),),
    )
    row = cur.fetchone()
    con.close()
    return row[0] if row else None
