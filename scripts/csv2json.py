import argparse
import csv
import json
from pathlib import Path
import sys

def infer_value(s: str):
    if s is None:
        return None
    s = s.strip()
    if s == "":
        return None
    low = s.lower()
    if low in ("true", "false"):
        return low == "true"
    # integer
    try:
        if s.isdigit() or (s.startswith("-") and s[1:].isdigit()):
            return int(s)
    except Exception:
        pass
    # float
    try:
        return float(s)
    except Exception:
        return s

def convert_csv_to_json(csv_path: Path, encoding: str = "utf-8", sep: str = ",", force: bool = False):
    json_path = csv_path.with_suffix(".json")
    if json_path.exists() and not force:
        print(f"Skipping existing: {json_path}")
        return
    with csv_path.open("r", encoding=encoding, newline="") as f:
        reader = csv.DictReader(f, delimiter=sep)
        rows = []
        for idx, r in enumerate(reader, start=1):
            obj = {}
            for k, v in r.items():
                if k is None:
                    continue
                # ignore "lang" column (case/whitespace insensitive)
                if k.strip().lower() == "lang":
                    continue
                if k.strip().lower() == "subs":
                    # remove next line characters from subs field
                    v = v.replace("\n", " ").replace("\r", " ")
                obj[k] = infer_value(v)
            # id cycles from 1..999999
            obj["id"] = ((idx - 1) % 999_999) + 1
            rows.append(obj)
    with json_path.open("w", encoding=encoding) as jf:
        json.dump(rows, jf, ensure_ascii=False, indent=2)
    print(f"Wrote: {json_path}")

def find_v1_dir(start: Path) -> Path:
    # default v1 is repo root / 'v1' where repo root is two levels up from this script
    # but allow overriding via CLI
    repo_root = start.resolve().parents[1]
    return repo_root / "v1"

def main(argv):
    p = argparse.ArgumentParser(description="Convert CSV files under /v1/ to JSON files saved beside the CSVs.")
    p.add_argument("--dir", "-d", type=Path, help="v1 directory to scan (defaults to repo/v1)", default=None)
    p.add_argument("--recursive", "-r", action="store_true", help="Recurse into subdirectories")
    p.add_argument("--sep", "-s", default=",", help="CSV delimiter (default ',')")
    p.add_argument("--encoding", default="utf-8", help="File encoding (default utf-8)")
    p.add_argument("--force", "-f", action="store_true", help="Overwrite existing JSON files")
    args = p.parse_args(argv)

    script_path = Path(__file__)
    v1_dir = args.dir if args.dir else find_v1_dir(script_path)
    if not v1_dir.exists() or not v1_dir.is_dir():
        print(f"v1 directory not found: {v1_dir}")
        return 2

    pattern = "**/*.csv" if args.recursive else "*.csv"
    files = list(v1_dir.glob(pattern))
    if not files:
        print("No CSV files found.")
        return 0

    for f in files:
        try:
            convert_csv_to_json(f, encoding=args.encoding, sep=args.sep, force=args.force)
        except Exception as e:
            print(f"Error converting {f}: {e}")

    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
