# app/database.py

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "dxcc.db")


def init_db():
    """Create database and tables if they don't exist; ensure new columns."""
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    # QSOs table
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS qsos (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            callsign    TEXT NOT NULL,
            country     TEXT NOT NULL,
            worked_call TEXT,
            qso_date    TEXT,
            qsl_status  TEXT,
            band        TEXT
        )
        """
    )

    # Users table (for auth)
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            callsign      TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL
        )
        """
    )

    # User profile table (bands + include_deleted)
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS user_profile (
            callsign        TEXT PRIMARY KEY,
            track_all       INTEGER NOT NULL DEFAULT 1,
            bands           TEXT,
            include_deleted INTEGER NOT NULL DEFAULT 0
        )
        """
    )

    # Ensure include_deleted column exists (upgrade path)
    cur.execute("PRAGMA table_info(user_profile)")
    cols = [row[1] for row in cur.fetchall()]
    if "include_deleted" not in cols:
        cur.execute(
            "ALTER TABLE user_profile "
            "ADD COLUMN include_deleted INTEGER NOT NULL DEFAULT 0"
        )

    con.commit()
    con.close()


# ---------------- QSOs ----------------

def get_qsos_for_user(callsign: str):
    """Return list of (country, worked_call, qso_date, qsl_status, band) for a callsign."""
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute(
        "SELECT country, worked_call, qso_date, qsl_status, band FROM qsos WHERE callsign = ?",
        (callsign.upper(),),
    )
    rows = cur.fetchall()
    con.close()
    return rows


def add_qso(callsign, country, worked_call, qso_date, qsl_status, band):
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute(
        """
        INSERT INTO qsos (callsign, country, worked_call, qso_date, qsl_status, band)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (callsign.upper(), country, worked_call, qso_date, qsl_status, band),
    )
    con.commit()
    con.close()


def delete_qso(callsign, country, worked_call, qso_date, qsl_status, band):
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute(
        """
        DELETE FROM qsos
        WHERE callsign = ? AND country = ? AND worked_call = ? AND qso_date = ?
              AND qsl_status = ? AND IFNULL(band, '') = IFNULL(?, '')
        """,
        (callsign.upper(), country, worked_call, qso_date, qsl_status, band),
    )
    con.commit()
    con.close()


def update_qso(callsign, old_row, new_row):
    """
    old_row / new_row are [country, worked_call, qso_date, qsl_status, band]
    """
    old_country, old_call, old_date, old_status, old_band = old_row
    country, call, date, status, band = new_row

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute(
        """
        UPDATE qsos
        SET country = ?, worked_call = ?, qso_date = ?, qsl_status = ?, band = ?
        WHERE callsign = ?
          AND country = ? AND worked_call = ? AND qso_date = ?
          AND qsl_status = ? AND IFNULL(band, '') = IFNULL(?, '')
        """,
        (
            country,
            call,
            date,
            status,
            band,
            callsign.upper(),
            old_country,
            old_call,
            old_date,
            old_status,
            old_band,
        ),
    )
    con.commit()
    con.close()


# --------------- USER PROFILE (bands + deleted toggle) ---------------

def get_user_profile(callsign: str):
    """
    Return (track_all: bool, bands: list[str], include_deleted: bool) for user.
    If no profile row, default to track_all=True, bands=[], include_deleted=False.
    """
    callsign = callsign.upper()
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute(
        "SELECT track_all, bands, include_deleted FROM user_profile WHERE callsign=?",
        (callsign,),
    )
    row = cur.fetchone()
    con.close()

    if not row:
        return True, [], False  # defaults

    track_all = bool(row[0])
    bands_str = row[1] or ""
    bands = [b for b in bands_str.split(",") if b.strip()]
    include_deleted = bool(row[2]) if row[2] is not None else False

    return track_all, bands, include_deleted


def set_user_profile(callsign: str, track_all: bool, bands: list[str], include_deleted: bool):
    callsign = callsign.upper()
    bands_str = ",".join(sorted(set(bands))) if bands else ""

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute(
        """
        INSERT INTO user_profile (callsign, track_all, bands, include_deleted)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(callsign) DO UPDATE SET
            track_all=excluded.track_all,
            bands=excluded.bands,
            include_deleted=excluded.include_deleted
        """,
        (callsign, 1 if track_all else 0, bands_str, 1 if include_deleted else 0),
    )
    con.commit()
    con.close()
