"""
CTY.DAT Import Module
Downloads and imports callsign prefix data from country-files.com

This provides comprehensive prefix coverage for amateur radio callsigns worldwide.
"""

import requests
import sqlite3
import re
from datetime import datetime, UTC
from typing import List, Tuple, Dict
from app.config import DB_PATH

CTY_URL = "https://www.country-files.com/cty/cty.dat"


def download_cty_dat() -> str:
    """Download CTY.DAT file from country-files.com"""
    try:
        response = requests.get(CTY_URL, timeout=30)
        response.raise_for_status()
        return response.text
    except Exception as e:
        raise Exception(f"Failed to download CTY.DAT: {e}")


def parse_cty_dat(content: str) -> List[Dict]:
    """
    Parse CTY.DAT format into structured data.
    
    Format:
    Country Name:CQ:ITU:Continent:Latitude:Longitude:GMT_offset:DXCC_prefix:
        prefix1,prefix2,prefix3;
    
    Returns list of dicts with entity and prefix info.
    """
    entities = []
    lines = content.split('\n')
    
    current_entity = None
    current_prefixes = []
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        if not line:
            i += 1
            continue
        
        # Check if this is a main entity line (contains multiple colons and ends with colon)
        if line.count(':') >= 7 and line.endswith(':'):
            # Save previous entity if exists
            if current_entity and current_prefixes:
                entities.append({
                    'entity': current_entity,
                    'prefixes': current_prefixes
                })
            
            # Parse new entity line
            parts = line.split(':')
            if len(parts) >= 8:
                current_entity = {
                    'name': parts[0].strip(),
                    'cq_zone': parts[1].strip(),
                    'itu_zone': parts[2].strip(),
                    'continent': parts[3].strip(),
                    'latitude': parts[4].strip(),
                    'longitude': parts[5].strip(),
                    'gmt_offset': parts[6].strip(),
                    'main_prefix': parts[7].strip(),
                }
                current_prefixes = []
        
        # Check if this is a prefix line (starts with whitespace)
        elif line and current_entity:
            # This line contains prefixes
            # Remove semicolon and split by comma
            prefix_text = line.rstrip(';')
            prefixes = [p.strip() for p in prefix_text.split(',') if p.strip()]
            
            for prefix in prefixes:
                if not prefix:
                    continue
                    
                # Handle special prefixes
                if prefix.startswith('='):
                    # Exact callsign match
                    current_prefixes.append({
                        'prefix': prefix[1:],
                        'exact': True
                    })
                elif prefix.startswith('['):
                    # Bracket notation
                    clean = prefix.strip('[]')
                    current_prefixes.append({
                        'prefix': clean,
                        'exact': False
                    })
                elif '(' in prefix:
                    # Has zone override - extract base prefix
                    base = prefix.split('(')[0]
                    current_prefixes.append({
                        'prefix': base,
                        'exact': False
                    })
                else:
                    # Regular prefix
                    current_prefixes.append({
                        'prefix': prefix,
                        'exact': False
                    })
        
        i += 1
    
    # Don't forget last entity
    if current_entity and current_prefixes:
        entities.append({
            'entity': current_entity,
            'prefixes': current_prefixes
        })
    
    return entities


def import_cty_to_database(entities: List[Dict]) -> Tuple[int, int]:
    """
    Import parsed CTY data into SQLite database.
    
    Returns (entities_imported, prefixes_imported)
    """
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    
    # Create a temporary table for new data
    cur.execute("""
        CREATE TABLE IF NOT EXISTS cty_entities (
            entity_id TEXT PRIMARY KEY,
            name TEXT,
            main_prefix TEXT,
            cq_zone INTEGER,
            itu_zone INTEGER,
            continent TEXT,
            active INTEGER DEFAULT 1
        )
    """)
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS cty_prefixes (
            prefix TEXT,
            entity_id TEXT,
            exact_match INTEGER DEFAULT 0,
            PRIMARY KEY (prefix, entity_id)
        )
    """)
    
    entities_count = 0
    prefixes_count = 0
    
    for item in entities:
        entity = item['entity']
        entity_id = entity['main_prefix']
        
        # Insert entity
        try:
            cur.execute("""
                INSERT OR REPLACE INTO cty_entities 
                (entity_id, name, main_prefix, cq_zone, itu_zone, continent)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                entity_id,
                entity['name'],
                entity['main_prefix'],
                int(entity['cq_zone']) if entity['cq_zone'].isdigit() else 0,
                int(entity['itu_zone']) if entity['itu_zone'].isdigit() else 0,
                entity['continent']
            ))
            entities_count += 1
        except Exception as e:
            print(f"Error inserting entity {entity_id}: {e}")
            continue
        
        # Insert prefixes
        for pfx in item['prefixes']:
            try:
                cur.execute("""
                    INSERT OR REPLACE INTO cty_prefixes 
                    (prefix, entity_id, exact_match)
                    VALUES (?, ?, ?)
                """, (
                    pfx['prefix'].upper(),
                    entity_id,
                    1 if pfx['exact'] else 0
                ))
                prefixes_count += 1
            except Exception as e:
                print(f"Error inserting prefix {pfx['prefix']}: {e}")
    
    # Track last update
    cur.execute("""
        CREATE TABLE IF NOT EXISTS cty_meta (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    
    cur.execute("""
        INSERT OR REPLACE INTO cty_meta (key, value)
        VALUES ('last_update', ?)
    """, (datetime.now(UTC).isoformat(),))
    
    con.commit()
    con.close()
    
    return entities_count, prefixes_count


def get_last_cty_update() -> str:
    """Get the last time CTY data was updated"""
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    
    try:
        cur.execute("SELECT value FROM cty_meta WHERE key='last_update'")
        row = cur.fetchone()
        con.close()
        
        if row:
            dt = datetime.fromisoformat(row[0])
            return dt.strftime("%Y-%m-%d %H:%M UTC")
        return "Never"
    except:
        con.close()
        return "Never"


def update_cty_data() -> Dict:
    """
    Main function to download and import CTY data.
    Returns dict with results.
    """
    try:
        # Download
        content = download_cty_dat()
        
        # Parse
        entities = parse_cty_dat(content)
        
        # Import
        entities_count, prefixes_count = import_cty_to_database(entities)
        
        return {
            'success': True,
            'entities': entities_count,
            'prefixes': prefixes_count,
            'timestamp': datetime.now(UTC).isoformat()
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }
