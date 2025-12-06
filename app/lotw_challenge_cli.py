from pathlib import Path

from app.lotw_challenge import parse_lotw_dxcc_csv, save_summary


def main():
    project_root = Path(__file__).resolve().parent
    data_dir = project_root / "data"

    csv_path = data_dir / "lotw_dxcc_credits.csv"
    json_path = data_dir / "lotw_challenge_summary.json"

    print(f"Using DXCC CSV: {csv_path}")
    summary = parse_lotw_dxcc_csv(csv_path)

    print("========================================")
    print("  LoTW DXCC / Challenge Summary")
    print("========================================")
    print(f"Total DXCC entities credited: {summary.total_entities}")
    print(f"Total band-entity 'Challenge slots': {summary.total_challenge_slots}")
    print()
    print("Entities by band:")
    for band, count in sorted(summary.entities_by_band.items()):
        print(f"  {band:>5}: {count}")

    print()
    print("Entities by mode:")
    for mode, count in sorted(summary.entities_by_mode.items()):
        print(f"  {mode:>6}: {count}")

    save_summary(summary, json_path)
    print()
    print(f"Summary written to: {json_path}")


if __name__ == "__main__":
    main()
