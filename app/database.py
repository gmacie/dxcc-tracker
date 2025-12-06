# app/database.py

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "dxcc.db")


def init_db():
    """Create database and tables if they don't exist."""
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    # QSOs for all users stored in one table
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS qsos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            callsign    TEXT NOT NULL,
            country     TEXT NOT NULL,
            worked_call TEXT,
            qso_date    TEXT,
            qsl_status  TEXT
        )
        """
    )

    # Users table for auth
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            callsign      TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL
        )
        """
    )

    con.commit()
    con.close()


def get_qsos_for_user(callsign: str):
    """Return list of (country, worked_call, qso_date, qsl_status) for a callsign."""
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute(
        "SELECT country, worked_call, qso_date, qsl_status FROM qsos WHERE callsign = ?",
        (callsign.upper(),),
    )
    rows = cur.fetchall()
    con.close()
    return rows


def add_qso(callsign, country, worked_call, qso_date, qsl_status):
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute(
        """
        INSERT INTO qsos (callsign, country, worked_call, qso_date, qsl_status)
        VALUES (?, ?, ?, ?, ?)
        """,
        (callsign.upper(), country, worked_call, qso_date, qsl_status),
    )
    con.commit()
    con.close()


def delete_qso(callsign, country, worked_call, qso_date, qsl_status):
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute(
        """
        DELETE FROM qsos
        WHERE callsign = ? AND country = ? AND worked_call = ? AND qso_date = ? AND qsl_status = ?
        """,
        (callsign.upper(), country, worked_call, qso_date, qsl_status),
    )
    con.commit()
    con.close()


def update_qso(callsign, old_row, new_row):
    """
    old_row / new_row are [country, worked_call, qso_date, qsl_status]
    """
    old_country, old_call, old_date, old_status = old_row
    country, call, date, status = new_row

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute(
        """
        UPDATE qsos
        SET country = ?, worked_call = ?, qso_date = ?, qsl_status = ?
        WHERE callsign = ?
          AND country = ? AND worked_call = ? AND qso_date = ? AND qsl_status = ?
        """,
        (
            country,
            call,
            date,
            status,
            callsign.upper(),
            old_country,
            old_call,
            old_date,
            old_status,
        ),
    )
    con.commit()
    con.close()
