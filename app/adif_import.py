# app/adif_import.py

import re
from datetime import datetime
from typing import List, Tuple

from app.database import add_qso, qso_exists


# -------------------------------------------------------------------
# Supported bands
# -------------------------------------------------------------------

SUPPORTED_BANDS = [
    "160m",
    "80m",
    "60m",
    "40m",
    "30m",
    "20m",
    "17m",
    "15m",
    "12m",
    "10m",
    "6m",
]


# -------------------------------------------------------------------
# ADIF parser
# -------------------------------------------------------------------

def parse_adif_file(path: str) -> List[Tuple[str, str, str, str, str]]:
    """
    Parse an ADIF file and return a list of tuples:
        (country, call_worked, date_yyyy_mm_dd, qsl_status, band)

    qsl_status is one of:
        - "Confirmed"
        - "Requested"
        - "Needed"
    """
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    # Split records on <EOR>
    records = re.split(r"<eor>", content, flags=re.IGNORECASE)

    results: List[Tuple[str, str, str, str, str]] = []

    for rec in records:
        rec = rec.strip()
        if not rec:
            continue

        fields = {}

        for m in re.finditer(
            r"<([^:>]+):(\d+)[^>]*>([^<]*)",
            rec,
            flags=re.IGNORECASE,
        ):
            tag = m.group(1).strip().upper()
            length = int(m.group(2))
            value = m.group(3)[:length].strip()
            fields[tag] = value

        call = fields.get("CALL", "").strip().upper()
        if not call:
            continue

        country = fields.get("COUNTRY", "").strip()

        # -----------------------------
        # Date
        # -----------------------------
        raw_date = fields.get("QSO_DATE", "")
        date_str = ""

        if len(raw_date) == 8 and raw_date.isdigit():
            try:
                dt = datetime.strptime(raw_date, "%Y%m%d")
                date_str = dt.strftime("%Y-%m-%d")
            except Exception:
                date_str = raw_date
        else:
            date_str = raw_date

        # -----------------------------
        # Band
        # -----------------------------
        raw_band = fields.get("BAND", "").lower().strip()
        band = ""

        if raw_band.endswith("m") or raw_band.endswith("cm"):
            for b in SUPPORTED_BANDS:
                if raw_band == b.lower():
                    band = b
                    break

        # -----------------------------
        # QSL status (LoTW / ARRL logic)
        # -----------------------------
        qsl_rcvd = fields.get("QSL_RCVD", "").upper()
        qsl_sent = fields.get("QSL_SENT", "").upper()
        eqsl_rcvd = fields.get("EQSL_QSL_RCVD", "").upper()
        lotw_rcvd = fields.get("LOTW_QSL_RCVD", "").upper()

        if qsl_rcvd in ("Y", "V") or eqsl_rcvd in ("Y", "V") or lotw_rcvd in ("Y", "V"):
            status = "Confirmed"
        elif qsl_sent in ("Y", "Q", "R"):
            status = "Requested"
        else:
            status = "Needed"

        results.append((country, call, date_str, status, band))

    return results


# -------------------------------------------------------------------
# Import into database
# -------------------------------------------------------------------

def import_adif(
    path: str,
    user: str,
    on_progress=None,     # callback(percent, message)
    on_done=None,         # callback()
    cancel_flag=None,
):
 
    """
    Import ADIF QSOs for a user.
    Skips duplicates automatically.
    """
    
    records = parse_adif_file(path)

    inserted = 0
    skipped = 0
    total = len(records)

    for i, (country, call, date, status, band) in enumerate(records, start=1):
        
        if cancel_flag and cancel_flag.get("value"):
            break
            
        if not date:
            continue

        existing = qso_exists(user, call, date, band)
        if existing:
            skipped += 1
            continue

        add_qso(
            user=user,
            country=country,
            call_worked=call,
            date=date,
            status=status,
            band=band,
        )
        inserted += 1
        
        # 🔹 Progress callback
        if on_progress:
            percent = int((i / total) * 100)
            on_progress(percent, f"Imported {i}/{total}")
            
    result = {
        "added": inserted,
        "skipped": skipped,
        "total": total,
    }

    # 🔹 Done callback
    if on_done:
        on_done(result)

    print(f"ADIF import complete for {user}: {inserted} added, {skipped} skipped")

    return result
