# app/auth.py

import hashlib
import sqlite3
from app.database import DB_PATH, init_db


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def register_user(callsign: str, password: str):
    callsign = callsign.strip().upper()
    password = password.strip()

    if not callsign or not password:
        return False, "Callsign and password required."

    init_db()  # ensure tables exist
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    try:
        cur.execute(
            "INSERT INTO users (callsign, password_hash) VALUES (?, ?)",
            (callsign, hash_password(password)),
        )
        con.commit()
        con.close()
        return True, "User created."
    except sqlite3.IntegrityError:
        con.close()
        return False, "Callsign already registered."


def authenticate(callsign: str, password: str):
    callsign = callsign.strip().upper()
    password = password.strip()

    init_db()
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute(
        "SELECT password_hash FROM users WHERE callsign = ?",
        (callsign,),
    )
    row = cur.fetchone()
    con.close()

    if not row:
        return False, "User not found."
    if row[0] != hash_password(password):
        return False, "Incorrect password."

    return True, "Login OK."
