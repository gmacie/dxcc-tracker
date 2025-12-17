import requests
import sqlite3
from datetime import datetime, UTC, timedelta

from app.config import DB_PATH

LOTW_PRIMARY_URL = "https://lotw.arrl.org/lotw-user-activity.csv"
LOTW_FALLBACK_URL = "https://www.hb9bza.net/lotw/lotw-user-activity.csv"

def _download_lotw_csv() -> str:
    try:
        r = requests.get(LOTW_PRIMARY_URL, timeout=30)
        r.raise_for_status()
        return r.text
    except Exception:
        r = requests.get(LOTW_FALLBACK_URL, timeout=30)
        r.raise_for_status()
        return r.text


def refresh_lotw_cache(force: bool = False):
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    # Check last refresh
    cur.execute("SELECT value FROM lotw_meta WHERE key='last_fetch'")
    row = cur.fetchone()

    if row and not force:
        last = datetime.fromisoformat(row[0])
        if datetime.now(UTC) - last < timedelta(days=1):
            con.close()
            return

    print("Refreshing LoTW user cache...")

    csv_text = _download_lotw_csv()
    lines = csv_text.splitlines()

    cur.execute("DELETE FROM lotw_users")

    for line in lines[1:]:  # skip header
        try:
            call, date = line.split(",")
            cur.execute(
                "INSERT INTO lotw_users VALUES (?, ?)",
                (call.strip().upper(), date.strip()),
            )
        except ValueError:
            continue

    cur.execute(
        "INSERT OR REPLACE INTO lotw_meta VALUES (?, ?)",
        ("last_fetch", datetime.now(UTC).isoformat()),
    )

    con.commit()
    con.close()

    print("LoTW cache refreshed.")
