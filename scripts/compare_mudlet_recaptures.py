#!/usr/bin/env python3

import argparse
import difflib
import json
import re
from collections import defaultdict
from pathlib import Path


def key(value):
    return re.sub(r"[^a-z0-9]+", "", (value or "").casefold())


def normalise_text(text):
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = []
    for line in text.split("\n"):
        line = re.sub(r"[ \t]+", " ", line).rstrip()
        lines.append(line)

    while lines and lines[0] == "":
        lines.pop(0)
    while lines and lines[-1] == "":
        lines.pop()

    return "\n".join(lines)


def strip_expected_time_variation(text):
    text = normalise_text(text)

    # Last-login relative dates naturally change as days pass.
    text = re.sub(
        r"Last login .*? ago(?: from [^\n.]+)?\.",
        "Last login <relative time>.",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    return text


def first_nonblank_line(text):
    for line in normalise_text(text).split("\n"):
        if line.strip():
            return line.strip()
    return ""


def find_hits(text):
    phrases = [
        "has arrived",
        "leaves",
        "narrates",
        "tells you",
        "says",
        "You are hungry.",
        "You are thirsty.",
        "MUME.Client protocol error",
    ]
    return [p for p in phrases if p in (text or "")]


def classify(previous_raw, latest_raw):
    previous = strip_expected_time_variation(previous_raw)
    latest = strip_expected_time_variation(latest_raw)

    if previous == latest:
        return "same_or_equivalent"

    prev_header = first_nonblank_line(previous)
    latest_header = first_nonblank_line(latest)

    if "No one by that name." in previous and latest.strip() == "No one by that name.":
        return "previous_not_found_with_extra_contamination"

    if previous.startswith(latest) and len(previous) > len(latest):
        return "previous_has_extra_after_clean_capture"

    if latest in previous and len(latest) > 0:
        return "latest_is_subset_of_previous_review_previous_extra"

    if prev_header and latest_header and prev_header == latest_header:
        return "same_header_but_body_differs_review"

    return "different_review"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--archive",
        default="/Users/Lewis/.config/mudlet/profiles/Multi-Users in Middle-earth/mume_whois_archive.json",
    )
    parser.add_argument("--names", required=True)
    parser.add_argument("--report", default="reports/mudlet_recapture_compare.md")
    args = parser.parse_args()

    archive_path = Path(args.archive)
    names_path = Path(args.names)
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    with archive_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    names = [
        line.strip()
        for line in names_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    wanted = {key(name): name for name in names}

    captures_by_key = defaultdict(list)

    for index, cap in enumerate(data.get("captures", []), start=1):
        q = cap.get("query_name") or ""
        parsed = cap.get("parsed") or {}

        possible_names = [
            q,
            parsed.get("query_name") or "",
            parsed.get("character_name") or "",
            parsed.get("display_name") or "",
        ]

        for name in possible_names:
            k = key(name)
            if k in wanted:
                captures_by_key[k].append((index, cap))
                break

    lines = []
    lines.append("# Mudlet Whois Recapture Comparison")
    lines.append("")
    lines.append(f"Archive: `{archive_path}`")
    lines.append(f"Names checked: {len(names)}")
    lines.append("")

    summary = defaultdict(int)

    for k, display_name in wanted.items():
        caps = captures_by_key.get(k, [])
        caps.sort(key=lambda pair: pair[0])

        lines.append(f"## {display_name}")
        lines.append("")

        if len(caps) < 2:
            summary["not_enough_captures"] += 1
            lines.append("Not enough captures to compare.")
            lines.append("")
            continue

        previous_index, previous = caps[-2]
        latest_index, latest = caps[-1]

        previous_raw = previous.get("raw_text") or ""
        latest_raw = latest.get("raw_text") or ""

        result = classify(previous_raw, latest_raw)
        summary[result] += 1

        lines.append(f"- Previous capture index: `{previous_index}`")
        lines.append(f"- Previous capture_id: `{previous.get('capture_id')}`")
        lines.append(f"- Previous quality: `{previous.get('capture_quality')}`")
        lines.append(f"- Latest capture index: `{latest_index}`")
        lines.append(f"- Latest capture_id: `{latest.get('capture_id')}`")
        lines.append(f"- Latest quality: `{latest.get('capture_quality')}`")
        lines.append(f"- Classification: **{result}**")
        lines.append(f"- Previous phrase hits: `{', '.join(find_hits(previous_raw)) or 'none'}`")
        lines.append(f"- Latest phrase hits: `{', '.join(find_hits(latest_raw)) or 'none'}`")
        lines.append("")

        prev_norm = strip_expected_time_variation(previous_raw).splitlines()
        latest_norm = strip_expected_time_variation(latest_raw).splitlines()

        diff = list(
            difflib.unified_diff(
                prev_norm,
                latest_norm,
                fromfile=f"previous:{previous_index}",
                tofile=f"latest:{latest_index}",
                lineterm="",
            )
        )

        lines.append("<details>")
        lines.append("<summary>Diff</summary>")
        lines.append("")
        lines.append("```diff")
        lines.extend(diff[:300])
        if len(diff) > 300:
            lines.append("... diff truncated ...")
        lines.append("```")
        lines.append("")
        lines.append("</details>")
        lines.append("")

    lines.append("# Summary")
    lines.append("")
    for k, v in sorted(summary.items()):
        lines.append(f"- {k}: {v}")

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Wrote report: {report_path}")
    print("Summary:")
    for k, v in sorted(summary.items()):
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
