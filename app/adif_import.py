# app/adif_import.py

import re
from datetime import datetime
from typing import List, Tuple


def parse_adif_file(path: str) -> List[Tuple[str, str, str, str]]:
    """
    Parse a basic ADIF file and return a list of
    (country, callsign, date_yyyy_mm_dd, status) tuples.

    status is mapped to: "Needed", "Requested", "Confirmed"
    """
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    # Split into records by <eor> (end of record)
    records = re.split(r"<eor>", content, flags=re.IGNORECASE)
    result = []

    for rec in records:
        rec = rec.strip()
        if not rec:
            continue

        # Extract fields of the form <TAG:len>value
        fields = {}
        for m in re.finditer(r"<([^:>]+):(\d+)[^>]*>([^<]*)", rec, flags=re.IGNORECASE):
            tag = m.group(1).strip().upper()
            length = int(m.group(2))
            value = m.group(3)[:length].strip()
            fields[tag] = value

        call = fields.get("CALL", "")
        if not call:
            continue

        # COUNTRY from ADIF, fall back to empty string
        country = fields.get("COUNTRY", "").strip()

        # QSO_DATE is YYYYMMDD
        raw_date = fields.get("QSO_DATE", "")
        date_str = ""
        if len(raw_date) == 8 and raw_date.isdigit():
            try:
                dt = datetime.strptime(raw_date, "%Y%m%d")
                date_str = dt.strftime("%Y-%m-%d")
            except Exception:
                date_str = ""
        else:
            date_str = raw_date  # best-effort fallback

        # Map QSL status
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

        result.append((country, call, date_str, status))

    return result
