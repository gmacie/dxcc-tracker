from __future__ import annotations

import csv
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Set, Tuple


@dataclass
class ChallengeSummary:
    total_entities: int
    total_challenge_slots: int
    entities_by_band: Dict[str, int]
    entities_by_mode: Dict[str, int]
    raw_entity_set: Set[str]
    raw_band_entity_pairs: Set[Tuple[str, str]]


def parse_lotw_dxcc_csv(csv_path: Path) -> ChallengeSummary:
    """
    Parse a LoTW DXCC credits CSV export and compute a simple
    Challenge-like summary.

    NOTE: You may need to adjust column names to match your exact CSV.
    This implementation assumes column names similar to:
        - 'Entity' or 'DXCC Entity'
        - 'Band'
        - 'Mode'
    """
    if not csv_path.exists():
        raise FileNotFoundError(f"LoTW DXCC credits CSV not found at {csv_path}")

    entities: Set[str] = set()
    band_entity: Set[Tuple[str, str]] = set()
    entities_by_band: Dict[str, Set[str]] = {}
    entities_by_mode: Dict[str, Set[str]] = {}

    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        # Normalize headers to lower-case for matching
        headers_lower = [h.lower() for h in reader.fieldnames or []]

        def pick_col(candidates):
            for c in candidates:
                if c in headers_lower:
                    return c
            return None

        entity_col = pick_col(["entity", "dxcc entity", "dxcc"])
        band_col = pick_col(["band"])
        mode_col = pick_col(["mode"])

        if not entity_col or not band_col:
            raise ValueError(
                "Could not detect expected columns in DXCC CSV. "
                f"Headers found: {reader.fieldnames}"
            )

        for row in reader:
            # Map row with lower-case keys
            row_l = {k.lower(): v for k, v in row.items()}

            entity = row_l.get(entity_col, "").strip()
            band = row_l.get(band_col, "").strip()
            mode = row_l.get(mode_col, "").strip() if mode_col else ""

            if not entity:
                continue

            entities.add(entity)

            if band:
                band_entity.add((band, entity))
                entities_by_band.setdefault(band, set()).add(entity)

            if mode:
                entities_by_mode.setdefault(mode, set()).add(entity)

    summary = ChallengeSummary(
        total_entities=len(entities),
        total_challenge_slots=len(band_entity),
        entities_by_band={b: len(s) for b, s in entities_by_band.items()},
        entities_by_mode={m: len(s) for m, s in entities_by_mode.items()},
        raw_entity_set=entities,
        raw_band_entity_pairs=band_entity,
    )
    return summary


def save_summary(summary: ChallengeSummary, json_path: Path) -> None:
    """Save the summary to JSON (with raw sets converted to sorted lists)."""
    data = asdict(summary)
    # Convert sets to sorted lists for JSON
    data["raw_entity_set"] = sorted(list(summary.raw_entity_set))
    data["raw_band_entity_pairs"] = sorted(
        [list(p) for p in summary.raw_band_entity_pairs],
        key=lambda x: (x[0], x[1]),
    )
    json_path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_summary(json_path: Path) -> ChallengeSummary:
    """Load a previously saved summary JSON."""
    data = json_path.read_text(encoding="utf-8")
    obj = json.loads(data)

    return ChallengeSummary(
        total_entities=obj["total_entities"],
        total_challenge_slots=obj["total_challenge_slots"],
        entities_by_band=obj["entities_by_band"],
        entities_by_mode=obj["entities_by_mode"],
        raw_entity_set=set(obj["raw_entity_set"]),
        raw_band_entity_pairs={tuple(p) for p in obj["raw_band_entity_pairs"]},
    )
