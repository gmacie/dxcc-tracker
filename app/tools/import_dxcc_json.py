import json
import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(BASE_DIR, "dxcc.db")
DXCC_JSON = os.path.join(DATA_DIR, "dxcc.json")




def import_dxcc():
    
    entity_count = 0
    active_count = 0
    prefix_count = 0

    if not os.path.exists(DXCC_JSON):
        raise FileNotFoundError("dxcc.json not found")

    with open(DXCC_JSON, "r", encoding="utf-8") as f:
        root = json.load(f)

    if "dxcc" not in root or not isinstance(root["dxcc"], list):
        raise ValueError("Invalid dxcc.json format (missing 'dxcc' list)")

    dxcc_list = root["dxcc"]

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    # Create tables
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS dxcc_entities (
            entity_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            active INTEGER NOT NULL
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS dxcc_prefixes (
            prefix TEXT NOT NULL,
            entity_id TEXT NOT NULL
        )
        """
    )

    # Clear old data
    cur.execute("DELETE FROM dxcc_entities")
    cur.execute("DELETE FROM dxcc_prefixes")

    entity_count = 0
    prefix_count = 0

    for ent in dxcc_list:
        if not isinstance(ent, dict):
            continue

        entity_id = str(ent.get("entityCode"))
        name = ent.get("name", "Unknown")
        deleted = bool(ent.get("deleted", False))
        active = 0 if deleted else 1
        
        if active:
            active_count += 1

        cur.execute(
            "INSERT INTO dxcc_entities (entity_id, name, active) VALUES (?, ?, ?)",
            (entity_id, name, active),
        )
        entity_count += 1

        prefix_str = ent.get("prefix", "")
        if prefix_str:
            prefixes = [
                p.strip().upper()
                for p in prefix_str.split(",")
                if p.strip()
            ]
            for p in prefixes:
                cur.execute(
                    "INSERT INTO dxcc_prefixes (prefix, entity_id) VALUES (?, ?)",
                    (p, entity_id),
                )
                prefix_count += 1

    con.commit()
    con.close()

    print(
        f"DXCC import complete: "
        f"{active_count} active / {entity_count} total entities, "
        f"{prefix_count} prefixes"
    )



if __name__ == "__main__":
    import_dxcc()
