"""
We have a json file containing a list of items, each with various attributes.
[
  {
    "url": "oRgN9I8vp4k",
    "time": 277,
    "subs": "Denn es gibt zwar viele schwarze Löcher mit bis zu 150 Sonnenmassen und auch welche mit der millionenfachen Masse der Sonne",
    "id": 1
  },    

This script remove items using regex that corresponds to subs, e.g. "criteria = \d{3}" removes items with three-digit numbers in the subs field.

Arguments:
--input: Path to the input JSON file.

The result will be saved to `/output/{timestamp}/{initial_name}_filtered.json`.

e.g. : python scripts/filter_items.py --input v1/en.json -c '\d{3}' -c 'billion' -I
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Sequence


def _repo_root() -> Path:
  """Return the repository root assuming this file lives in scripts/."""
  return Path(__file__).resolve().parents[1]


def _load_items(path: Path) -> List[dict]:
  with path.open("r", encoding="utf-8") as fh:
    data = json.load(fh)
  if not isinstance(data, list):
    raise ValueError(f"Expected a list in {path}, got {type(data).__name__}")
  return data


def _compile_patterns(patterns: Sequence[str], ignore_case: bool) -> List[re.Pattern]:
  flags = re.IGNORECASE if ignore_case else 0
  return [re.compile(p, flags) for p in patterns]


def _matches_any(subs: str, patterns: Iterable[re.Pattern]) -> bool:
  return any(p.search(subs) for p in patterns)


def filter_items(
  items: List[dict],
  patterns: Sequence[str],
  ignore_case: bool = False,
) -> tuple[List[dict], List[dict]]:
  compiled = _compile_patterns(patterns, ignore_case)
  kept: List[dict] = []
  removed: List[dict] = []

  for item in items:
    subs = item.get("subs")
    if isinstance(subs, str) and _matches_any(subs, compiled):
      removed.append(item)
    else:
      kept.append(item)

  return kept, removed


def build_output_path(input_path: Path, output_dir: Path | None) -> Path:
  base_dir = output_dir if output_dir else _repo_root() / "output"
  timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
  target_dir = base_dir / timestamp
  target_dir.mkdir(parents=True, exist_ok=True)
  return target_dir / f"{input_path.stem}_filtered.json"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
  parser = argparse.ArgumentParser(
    description="Filter out items whose 'subs' match one or more regex criteria."
  )
  parser.add_argument("--input", "-i", type=Path, required=True, help="Input JSON file")
  parser.add_argument(
    "--criteria",
    "-c",
    action="append",
    required=True,
    help="Regex applied to the 'subs' field. Can be passed multiple times.",
  )
  parser.add_argument(
    "--ignore-case",
    "-I",
    action="store_true",
    help="Apply regexes case-insensitively.",
  )
  parser.add_argument(
    "--output-dir",
    "-o",
    type=Path,
    default=None,
    help="Base output directory (defaults to repo/output)",
  )
  return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
  args = parse_args(argv)
  input_path: Path = args.input

  if not input_path.exists():
    print(f"Input not found: {input_path}")
    return 1

  try:
    items = _load_items(input_path)
  except Exception as exc:  # pragma: no cover - defensive
    print(f"Failed to load JSON: {exc}")
    return 1

  kept, removed = filter_items(items, args.criteria, ignore_case=args.ignore_case)

  out_path = build_output_path(input_path, args.output_dir)
  with out_path.open("w", encoding="utf-8") as fh:
    json.dump(kept, fh, ensure_ascii=False, indent=2)

  print(f"Loaded {len(items)} items from {input_path}")
  print(f"Removed {len(removed)} items using {len(args.criteria)} pattern(s)")
  print(f"Kept {len(kept)} items -> {out_path}")

  return 0


if __name__ == "__main__":  # pragma: no cover
  raise SystemExit(main())
