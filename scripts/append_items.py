"""
Merge JSON item lists while avoiding duplicate subtitles and keeping ids unique.

Features:
- Avoid adding items whose `subs` already exists in the base file.
- Assign fresh, non-conflicting ids to newly appended items.

Args:
    --base_file: Path to the base JSON file, e.g. v1/en.json
    --append_file: Path to the JSON file to append, e.g. v2/en_extra.json
    --output: Optional output path (defaults to overwriting the base file)
    --dry-run: Report what would happen without writing anything
    
Example:
    python scripts/append_items.py \
        --base_file v1/en.json \
        --append_file output/en_extra.json \
        --output v3/en_merged.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable, List, Sequence, Set, Tuple


def _load_items(path: Path) -> List[dict]:
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, list):
        raise ValueError(f"Expected a list in {path}, got {type(data).__name__}")
    return data


def _normalize_subs(subs: object) -> str | None:
    if not isinstance(subs, str):
        return None
    normalized = " ".join(subs.split()).strip().lower()
    return normalized or None


def _collect_existing_state(items: Iterable[dict]) -> Tuple[Set[str], Set[int], int]:
    seen_subs: Set[str] = set()
    used_ids: Set[int] = set()
    max_id = 0

    for item in items:
        norm = _normalize_subs(item.get("subs"))
        if norm:
            seen_subs.add(norm)
        item_id = item.get("id")
        if isinstance(item_id, int):
            used_ids.add(item_id)
            if item_id > max_id:
                max_id = item_id

    return seen_subs, used_ids, max_id


def merge_items(base_items: List[dict], new_items: List[dict]) -> Tuple[List[dict], List[dict], List[dict]]:
    """Return merged list, added items, and skipped duplicates."""

    seen_subs, used_ids, max_id = _collect_existing_state(base_items)
    next_id = (max_id + 1) if used_ids else 1

    added: List[dict] = []
    skipped: List[dict] = []

    for item in new_items:
        norm = _normalize_subs(item.get("subs"))
        if norm and norm in seen_subs:
            skipped.append(item)
            continue

        new_item = dict(item)

        # Guarantee a unique id for the merged set.
        while next_id in used_ids:
            next_id += 1
        new_item["id"] = next_id
        used_ids.add(next_id)
        next_id += 1

        if norm:
            seen_subs.add(norm)
        added.append(new_item)

    merged = base_items + added
    return merged, added, skipped


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Append items from another JSON list while deduping by 'subs'."
    )
    parser.add_argument("--base_file", "-b", type=Path, required=True, help="Base JSON file")
    parser.add_argument(
        "--append_file", "-a", type=Path, required=True, help="JSON file to append"
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=None,
        help="Where to write the merged file (defaults to overwriting the base file)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute merge and print stats without writing output",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)

    base_path: Path = args.base_file
    append_path: Path = args.append_file
    output_path: Path = args.output if args.output else base_path

    for path in (base_path, append_path):
        if not path.exists():
            print(f"File not found: {path}")
            return 1

    try:
        base_items = _load_items(base_path)
        append_items = _load_items(append_path)
    except Exception as exc:  # pragma: no cover - defensive
        print(f"Failed to load JSON: {exc}")
        return 1

    merged, added, skipped = merge_items(base_items, append_items)

    print(f"Base items:   {len(base_items)} from {base_path}")
    print(f"Append items: {len(append_items)} from {append_path}")
    print(f"Added:        {len(added)}")
    print(f"Skipped dupes:{len(skipped)} (matched by 'subs')")

    if args.dry_run:
        print("Dry run enabled; no file written.")
        return 0

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fh:
        json.dump(merged, fh, ensure_ascii=False, indent=2)

    print(f"Wrote {len(merged)} items to {output_path}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())