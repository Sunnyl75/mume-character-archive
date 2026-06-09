#!/usr/bin/env python3

import argparse
import json
import re
from pathlib import Path


def key(value):
    return re.sub(r"[^a-z0-9]+", "", (value or "").casefold())


def capture_keys(capture):
    parsed = capture.get("parsed") or {}
    values = [
        capture.get("query_name") or "",
        parsed.get("query_name") or "",
        parsed.get("character_name") or "",
        parsed.get("display_name") or "",
    ]
    return {key(v) for v in values if key(v)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--archive",
        default="/Users/Lewis/.config/mudlet/profiles/Multi-Users in Middle-earth/mume_whois_archive.json",
    )
    parser.add_argument("--names", required=True)
    parser.add_argument(
        "--output",
        default="/Users/Lewis/.config/mudlet/profiles/Multi-Users in Middle-earth/mume_whois_archive.import_cleaned.json",
    )
    args = parser.parse_args()

    archive_path = Path(args.archive)
    names_path = Path(args.names)
    output_path = Path(args.output)

    with archive_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    wanted_names = [
        line.strip()
        for line in names_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    wanted = {key(name): name for name in wanted_names}

    captures = data.get("captures", [])

    latest_for_name = {}

    for index, capture in enumerate(captures, start=1):
        keys = capture_keys(capture)
        matched = sorted(keys & set(wanted.keys()))

        for k in matched:
            quality = capture.get("capture_quality")
            if quality in {"high", "medium", "not_found"}:
                latest_for_name[k] = index

    downgraded = []

    for index, capture in enumerate(captures, start=1):
        keys = capture_keys(capture)
        matched = sorted(keys & set(wanted.keys()))

        if not matched:
            continue

        # If this capture is not the latest good/not_found capture for any matched
        # recapture name, mark it as superseded for import purposes.
        keep_for_any = any(latest_for_name.get(k) == index for k in matched)

        if not keep_for_any:
            old_quality = capture.get("capture_quality")
            capture["original_capture_quality_before_import_cleanup"] = old_quality
            capture["capture_quality"] = "low"
            capture["import_cleanup_status"] = "superseded_by_recapture"
            capture["import_cleanup_reason"] = (
                "Older capture for a recaptured suspicious name; "
                "kept in archive copy but downgraded so importer does not treat it as current."
            )

            superseded_by = []
            for k in matched:
                latest_index = latest_for_name.get(k)
                if latest_index:
                    latest_capture = captures[latest_index - 1]
                    superseded_by.append({
                        "name": wanted[k],
                        "capture_index": latest_index,
                        "capture_id": latest_capture.get("capture_id"),
                    })

            capture["superseded_by"] = superseded_by

            downgraded.append({
                "index": index,
                "query_name": capture.get("query_name"),
                "old_quality": old_quality,
                "capture_id": capture.get("capture_id"),
                "matched_names": [wanted[k] for k in matched],
                "superseded_by": superseded_by,
            })

    data["import_cleanup"] = {
        "kind": "recapture_supersession",
        "source_archive": str(archive_path),
        "recapture_names_file": str(names_path),
        "downgraded_capture_count": len(downgraded),
        "note": (
            "This file is an import-only cleaned copy. The original Mudlet archive "
            "should remain untouched as raw evidence."
        ),
    }

    output_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"Wrote cleaned import copy: {output_path}")
    print(f"Recapture names: {len(wanted_names)}")
    print(f"Downgraded older captures: {len(downgraded)}")
    print()

    for item in downgraded:
        print(
            f"#{item['index']} {item['query_name']} "
            f"{item['capture_id']} "
            f"{item['old_quality']} -> low"
        )


if __name__ == "__main__":
    main()
