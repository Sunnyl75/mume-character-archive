#!/usr/bin/env python3
"""
Build the Mudlet whois queue export from data/working/whois_queue.csv.

This script reads:

    data/working/whois_queue.csv

and writes:

    exports/mudlet/whois_queue.txt

The output is a simple one-character-name-per-line text file, intended for
use by Mudlet scripts that will collect MUME whois data.

By default, names already marked as checked are skipped.

Run from the repository root:

    python3 scripts/build_whois_queue.py

Options:

    --include-checked
        Include names even if already_checked is yes/true/1.

    --limit N
        Export only the first N queued names.

    --priority VALUE
        Export only rows matching a given priority value.

    --output PATH
        Write to a different output path.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = REPO_ROOT / "data" / "working" / "whois_queue.csv"
DEFAULT_OUTPUT = REPO_ROOT / "exports" / "mudlet" / "whois_queue.txt"


CHECKED_VALUES = {"yes", "true", "1", "checked", "done"}


def clean(value: object) -> str:
    if value is None:
        return ""

    return str(value).strip()


def is_checked(value: object) -> bool:
    return clean(value).casefold() in CHECKED_VALUES


def read_queue(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Missing input file: {path}")

    with path.open("r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)

        if not reader.fieldnames:
            raise ValueError(f"Input file has no header row: {path}")

        required = {"character_name"}
        missing = required - set(reader.fieldnames)

        if missing:
            raise ValueError(
                f"{path} is missing required column(s): {', '.join(sorted(missing))}"
            )

        return list(reader)


def build_names(
    rows: list[dict[str, str]],
    include_checked: bool,
    priority: str | None,
    limit: int | None,
) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()

    for row in rows:
        name = clean(row.get("character_name"))

        if not name:
            continue

        if not include_checked and is_checked(row.get("already_checked")):
            continue

        if priority is not None:
            row_priority = clean(row.get("priority"))
            if row_priority != priority:
                continue

        # Keep first occurrence only. MUME character names are unique at a given
        # time, but historical duplicate associations may exist in research data.
        key = name.casefold()
        if key in seen:
            continue

        seen.add(key)
        names.append(name)

        if limit is not None and len(names) >= limit:
            break

    return names


def write_names(path: Path, names: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(names) + ("\n" if names else ""), encoding="utf-8")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build exports/mudlet/whois_queue.txt from data/working/whois_queue.csv"
    )

    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help="Input CSV path. Default: data/working/whois_queue.csv",
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Output text path. Default: exports/mudlet/whois_queue.txt",
    )

    parser.add_argument(
        "--include-checked",
        action="store_true",
        help="Include rows already marked as checked.",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Export only the first N names after filtering.",
    )

    parser.add_argument(
        "--priority",
        type=str,
        default=None,
        help="Export only rows matching this priority value.",
    )

    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)

    try:
        rows = read_queue(args.input)
        names = build_names(
            rows=rows,
            include_checked=args.include_checked,
            priority=args.priority,
            limit=args.limit,
        )
        write_names(args.output, names)

    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"Wrote {len(names)} character name(s) to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
