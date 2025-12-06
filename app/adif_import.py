# app/adif_import.py

import re
from datetime import datetime
from typing import List, Tuple

# Supported bands in this app
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


def parse_adif_file(path: str) -> List[Tuple[str, str, str, str, str]]:
    """
    Parse a basic ADIF file and return a list of
    (country, callsign, date_yyyy_mm_dd, status, band) tuples.

    status is mapped to: "Needed", "Requested", "Confirmed"
    band is normalized to one of SUPPORTED_BANDS or "" if not mapped.
    """
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    # Split into records by <EOR>
    records = re.split(r"<eor>", content, flags=re.IGNORECASE)
    result: List[Tuple[str, str, str, str, str]] = []

    for rec in records:
        rec = rec.strip()
        if not rec:
            continue

        fields = {}
        # Match fields like <TAG:len>value
        for m in re.finditer(r"<([^:>]+):(\d+)[^>]*>([^<]*)", rec, flags=re.IGNORECASE):
            tag = m.group(1).strip().upper()
            length = int(m.group(2))
            value = m.group(3)[:length].strip()
            fields[tag] = value

        call = fields.get("CALL", "").strip()
        if not call:
            continue

        country = fields.get("COUNTRY", "").strip()

        # Date
        raw_date = fields.get("QSO_DATE", "").strip()
        date_str = ""
        if len(raw_date) == 8 and raw_date.isdigit():
            try:
                dt = datetime.strptime(raw_date, "%Y%m%d")
                date_str = dt.strftime("%Y-%m-%d")
            except Exception:
                date_str = raw_date
        else:
            date_str = raw_date

        # Band
        raw_band = fields.get("BAND", "").lower().strip()
        band = ""
        if raw_band.endswith("m") or raw_band.endswith("cm"):
            # Normalize like "20m", "6m" etc.
            band_candidate = raw_band
        else:
            band_candidate = ""

        if band_candidate in [b.lower() for b in SUPPORTED_BANDS]:
            # Map back to the canonical case (e.g. "20m")
            for b in SUPPORTED_BANDS:
                if b.lower() == band_candidate:
                    band = b
                    break
        else:
            band = ""  # unsupported or missing

        # QSL status mapping
        qsl_rcvd = fields.get("QSL_RCVD", "").upper()
        qsl_sent = fields.get("QSL_SENT", "").upper()
        eqsl_qsl_rcvd = fields.get("EQSL_QSL_RCVD", "").upper()
        lotw_qsl_rcvd = fields.get("LOTW_QSL_RCVD", "").upper()

        if qsl_rcvd in ("Y", "V") or eqsl_qsl_rcvd in ("Y", "V") or lotw_qsl_rcvd in ("Y", "V"):
            status = "Confirmed"
        elif qsl_sent in ("Y", "Q", "R"):
            status = "Requested"
        else:
            status = "Needed"

        result.append((country, call, date_str, status, band))

    return result
