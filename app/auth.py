import json
import os
import hashlib

USERS_FILE = os.path.join("userdata", "users.json")


def _ensure_userdata():
    os.makedirs("userdata", exist_ok=True)


def load_users():
    _ensure_userdata()
    if not os.path.exists(USERS_FILE):
        return {}
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_users(users):
    _ensure_userdata()
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=4)


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def register_user(callsign: str, password: str):
    callsign = callsign.strip().upper()
    password = password.strip()
    if not callsign or not password:
        return False, "Callsign and password required."

    users = load_users()
    if callsign in users:
        return False, "Callsign already registered."

    users[callsign] = {"password": hash_password(password)}
    save_users(users)
    return True, "User created."


def authenticate(callsign: str, password: str):
    callsign = callsign.strip().upper()
    password = password.strip()
    users = load_users()

    if callsign not in users:
        return False, "User not found."
    if users[callsign]["password"] != hash_password(password):
        return False, "Incorrect password."

    return True, "Login OK."
