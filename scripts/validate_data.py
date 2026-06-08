#!/usr/bin/env python3
"""
Validate the MUME Character Archive working data.

This validator is intentionally evidence-friendly:
- It allows partial historical data.
- It allows characters with no known player.
- It allows logs with uncertain dates.
- It allows the current first-pass CSV structure produced from PLAYERS.TXT.
- It fails only on structural problems that would make the archive inconsistent.

Run from the repository root:

    python3 scripts/validate_data.py
"""

from __future__ import annotations

import csv
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKING_DIR = REPO_ROOT / "data" / "working"


@dataclass
class Issue:
    level: str
    file: str
    message: str


class Validator:
    def __init__(self) -> None:
        self.issues: list[Issue] = []
        self.tables: dict[str, list[dict[str, str]]] = {}

    def error(self, file: str, message: str) -> None:
        self.issues.append(Issue("ERROR", file, message))

    def warning(self, file: str, message: str) -> None:
        self.issues.append(Issue("WARNING", file, message))

    def info(self, file: str, message: str) -> None:
        self.issues.append(Issue("INFO", file, message))

    def read_csv(
        self,
        filename: str,
        required_columns: Iterable[str],
        optional_columns: Iterable[str] = (),
    ) -> list[dict[str, str]]:
        path = WORKING_DIR / filename

        if not path.exists():
            self.error(filename, f"Missing required file: {path}")
            self.tables[filename] = []
            return []

        try:
            with path.open("r", newline="", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                fieldnames = reader.fieldnames or []

                missing = [col for col in required_columns if col not in fieldnames]
                if missing:
                    self.error(filename, f"Missing required column(s): {', '.join(missing)}")

                rows = list(reader)

        except Exception as exc:
            self.error(filename, f"Could not read CSV: {exc}")
            self.tables[filename] = []
            return []

        self.tables[filename] = rows
        return rows

    def first_existing_column(self, filename: str, rows: list[dict[str, str]], candidates: list[str]) -> str | None:
        if not rows:
            # Fall back to header lookup from stored table if possible.
            return candidates[0] if candidates else None

        available = set(rows[0].keys())

        for candidate in candidates:
            if candidate in available:
                return candidate

        self.warning(
            filename,
            f"None of these optional columns were found: {', '.join(candidates)}",
        )
        return None

    def check_unique_ids(self, filename: str, rows: list[dict[str, str]], id_column: str) -> set[str]:
        seen: set[str] = set()
        duplicates: set[str] = set()
        blanks = 0

        for row_number, row in enumerate(rows, start=2):
            value = clean(row.get(id_column))

            if not value:
                blanks += 1
                self.error(filename, f"Row {row_number} has blank {id_column}")
                continue

            if value in seen:
                duplicates.add(value)
            else:
                seen.add(value)

        for value in sorted(duplicates):
            self.error(filename, f"Duplicate {id_column}: {value}")

        if not duplicates and blanks == 0:
            self.info(filename, f"{id_column} values are unique")

        return seen

    def check_allowed_values(
        self,
        filename: str,
        rows: list[dict[str, str]],
        column: str,
        allowed_values: set[str],
        allow_blank: bool = True,
    ) -> None:
        if not rows:
            return

        if column not in rows[0]:
            # Some early-stage files do not yet have all planned columns.
            return

        for row_number, row in enumerate(rows, start=2):
            value = clean(row.get(column))

            if not value and allow_blank:
                continue

            if value not in allowed_values:
                self.error(
                    filename,
                    f"Row {row_number} has invalid {column} '{value}'. "
                    f"Allowed: {', '.join(sorted(allowed_values))}",
                )

    def check_date_range(
        self,
        filename: str,
        rows: list[dict[str, str]],
        start_column: str,
        end_column: str,
    ) -> None:
        if not rows:
            return

        if start_column not in rows[0] or end_column not in rows[0]:
            return

        for row_number, row in enumerate(rows, start=2):
            start_raw = clean(row.get(start_column))
            end_raw = clean(row.get(end_column))

            if not start_raw or not end_raw:
                continue

            start = parse_iso_date(start_raw)
            end = parse_iso_date(end_raw)

            if start is None:
                self.error(filename, f"Row {row_number} has invalid {start_column}: {start_raw}")

            if end is None:
                self.error(filename, f"Row {row_number} has invalid {end_column}: {end_raw}")

            if start is not None and end is not None and start > end:
                self.error(
                    filename,
                    f"Row {row_number} has date range start after end: {start_raw} > {end_raw}",
                )

    def check_optional_foreign_key(
        self,
        filename: str,
        rows: list[dict[str, str]],
        column: str,
        valid_ids: set[str],
        target_name: str,
    ) -> None:
        if not rows:
            return

        if column not in rows[0]:
            return

        for row_number, row in enumerate(rows, start=2):
            value = clean(row.get(column))

            if not value:
                continue

            values = split_multi_id_field(value)

            for item in values:
                if item not in valid_ids:
                    self.error(
                        filename,
                        f"Row {row_number} references missing {target_name} in {column}: {item}",
                    )

    def check_duplicate_character_names(
        self,
        characters: list[dict[str, str]],
        ambiguities: list[dict[str, str]],
    ) -> None:
        by_name: dict[str, list[str]] = {}

        for row in characters:
            character_id = clean(row.get("character_id"))
            name = clean(row.get("name"))

            if not name:
                continue

            key = name.casefold()
            by_name.setdefault(key, []).append(character_id)

        ambiguity_name_column = self.first_existing_column(
            "historical_ambiguities.csv",
            ambiguities,
            ["character_name", "name"],
        )

        ambiguity_names: set[str] = set()
        if ambiguity_name_column:
            ambiguity_names = {
                clean(row.get(ambiguity_name_column)).casefold()
                for row in ambiguities
                if clean(row.get(ambiguity_name_column))
            }

        for key, character_ids in sorted(by_name.items()):
            if len(character_ids) <= 1:
                continue

            display_name = key

            if key in ambiguity_names:
                self.info(
                    "characters.csv",
                    f"Repeated character name '{display_name}' is documented in historical_ambiguities.csv",
                )
            else:
                self.warning(
                    "characters.csv",
                    f"Repeated character name '{display_name}' is not documented in historical_ambiguities.csv. "
                    "This may be a transferred/shared early character, a deleted/recreated name, "
                    "or a data-entry issue.",
                )

    def check_unlinked_characters(
        self,
        characters: list[dict[str, str]],
        links: list[dict[str, str]],
    ) -> None:
        linked_character_ids = {
            clean(row.get("character_id"))
            for row in links
            if clean(row.get("character_id"))
        }

        unlinked = [
            clean(row.get("character_id"))
            for row in characters
            if clean(row.get("character_id")) and clean(row.get("character_id")) not in linked_character_ids
        ]

        if unlinked:
            self.warning(
                "characters.csv",
                f"{len(unlinked)} character(s) have no known player link yet. "
                "This is allowed for incomplete historical data.",
            )
        else:
            self.info("characters.csv", "All current characters have at least one player-character link")

    def validate(self) -> int:
        sources = self.read_csv(
            "sources.csv",
            [
                "source_id",
                "title",
                "source_type",
            ],
        )

        players = self.read_csv(
            "players.csv",
            [
                "player_id",
                "main_handle",
            ],
        )

        characters = self.read_csv(
            "characters.csv",
            [
                "character_id",
                "name",
            ],
        )

        links = self.read_csv(
            "player_character_links.csv",
            [
                "link_id",
                "player_id",
                "character_id",
                "link_type",
                "status",
                "confidence",
            ],
        )

        # Current package uses a slightly lighter evidence format than the future model.
        evidence = self.read_csv(
            "evidence.csv",
            [
                "evidence_id",
                "source_id",
                "evidence_type",
                "claim",
                "raw_text",
                "date_confidence",
                "confidence",
            ],
        )

        # Logs are currently empty scaffolding, so only require the columns that exist in the package.
        logs = self.read_csv(
            "logs.csv",
            [
                "log_id",
                "title",
                "filename",
                "date_exact",
                "date_confidence",
            ],
        )

        log_appearances = self.read_csv(
            "log_appearances.csv",
            [
                "appearance_id",
                "log_id",
                "character_id",
                "character_name",
                "line_excerpt",
                "event_type",
                "date_confidence",
                "confidence",
            ],
        )

        whois_queue = self.read_csv(
            "whois_queue.csv",
            [
                "character_id",
                "character_name",
            ],
        )

        whois_records = self.read_csv(
            "whois_records.csv",
            [
                "whois_id",
                "character_id",
                "character_name",
                "captured_at",
                "raw_text",
                "parsed_level",
                "parsed_race",
                "parsed_class",
                "status",
                "parse_confidence",
            ],
        )

        ambiguities = self.read_csv(
            "historical_ambiguities.csv",
            [
                "other_player_id",
                "other_main_handle",
                "ambiguity_type",
                "note",
            ],
        )

        source_ids = self.check_unique_ids("sources.csv", sources, "source_id")
        player_ids = self.check_unique_ids("players.csv", players, "player_id")
        character_ids = self.check_unique_ids("characters.csv", characters, "character_id")
        self.check_unique_ids("player_character_links.csv", links, "link_id")
        evidence_ids = self.check_unique_ids("evidence.csv", evidence, "evidence_id")

        if logs:
            self.check_unique_ids("logs.csv", logs, "log_id")

        if log_appearances:
            self.check_unique_ids("log_appearances.csv", log_appearances, "appearance_id")

        if whois_records:
            self.check_unique_ids("whois_records.csv", whois_records, "whois_id")

        # Foreign-key checks: strict when a reference is present.
        self.check_optional_foreign_key("players.csv", players, "primary_source_id", source_ids, "source_id")

        self.check_optional_foreign_key(
            "player_character_links.csv",
            links,
            "player_id",
            player_ids,
            "player_id",
        )
        self.check_optional_foreign_key(
            "player_character_links.csv",
            links,
            "character_id",
            character_ids,
            "character_id",
        )
        self.check_optional_foreign_key(
            "player_character_links.csv",
            links,
            "primary_evidence_id",
            evidence_ids,
            "evidence_id",
        )

        self.check_optional_foreign_key("evidence.csv", evidence, "source_id", source_ids, "source_id")

        log_ids = {
            clean(row.get("log_id"))
            for row in logs
            if clean(row.get("log_id"))
        }

        self.check_optional_foreign_key("log_appearances.csv", log_appearances, "log_id", log_ids, "log_id")
        self.check_optional_foreign_key(
            "log_appearances.csv",
            log_appearances,
            "character_id",
            character_ids,
            "character_id",
        )
        self.check_optional_foreign_key("whois_queue.csv", whois_queue, "character_id", character_ids, "character_id")
        self.check_optional_foreign_key("whois_queue.csv", whois_queue, "linked_player_id", player_ids, "player_id")
        self.check_optional_foreign_key(
            "whois_records.csv",
            whois_records,
            "character_id",
            character_ids,
            "character_id",
        )

        self.check_optional_foreign_key(
            "historical_ambiguities.csv",
            ambiguities,
            "current_player_id",
            player_ids,
            "player_id",
        )
        self.check_optional_foreign_key(
            "historical_ambiguities.csv",
            ambiguities,
            "other_player_id",
            player_ids,
            "player_id",
        )

        # Controlled vocabularies: deliberately broad and expandable.
        allowed_confidence = {
            "certain",
            "high",
            "medium",
            "low",
            "unknown",
            "needs_review",
        }

        allowed_link_status = {
            "accepted",
            "probable",
            "possible",
            "disputed",
            "rejected",
            "needs_review",
        }

        allowed_link_type = {
            "listed_same_player",
            "manual_research_link",
            "whois_inferred",
            "log_inferred",
            "possible_transfer",
            "possible_name_reuse",
            "possible_transfer_or_name_reuse",
            "disputed",
            "unknown",
        }

        allowed_date_confidence = {
            "exact",
            "bounded",
            "before_date",
            "after_date",
            "inferred",
            "unknown",
            "none",
            "undated_source",
        }

        allowed_booleanish = {
            "yes",
            "no",
            "true",
            "false",
            "0",
            "1",
            "unknown",
            "",
        }

        self.check_allowed_values("player_character_links.csv", links, "status", allowed_link_status)
        self.check_allowed_values("player_character_links.csv", links, "confidence", allowed_confidence)
        self.check_allowed_values("player_character_links.csv", links, "link_type", allowed_link_type)

        self.check_allowed_values("evidence.csv", evidence, "confidence", allowed_confidence)
        self.check_allowed_values("evidence.csv", evidence, "date_confidence", allowed_date_confidence)

        self.check_allowed_values("logs.csv", logs, "date_confidence", allowed_date_confidence)
        self.check_allowed_values("log_appearances.csv", log_appearances, "date_confidence", allowed_date_confidence)
        self.check_allowed_values("log_appearances.csv", log_appearances, "confidence", allowed_confidence)

        self.check_allowed_values("whois_records.csv", whois_records, "parse_confidence", allowed_confidence)
        self.check_allowed_values("whois_queue.csv", whois_queue, "already_checked", allowed_booleanish)

        # Dates: permissive about blanks and absent columns, strict about malformed or impossible ranges.
        self.check_date_range("characters.csv", characters, "first_seen", "last_seen")
        self.check_date_range("evidence.csv", evidence, "date_start", "date_end")
        self.check_date_range("logs.csv", logs, "date_start", "date_end")
        self.check_date_range("log_appearances.csv", log_appearances, "date_start", "date_end")

        # Research-friendly warnings.
        self.check_unlinked_characters(characters, links)
        self.check_duplicate_character_names(characters, ambiguities)

        return self.print_report()

    def print_report(self) -> int:
        error_count = sum(1 for issue in self.issues if issue.level == "ERROR")
        warning_count = sum(1 for issue in self.issues if issue.level == "WARNING")
        info_count = sum(1 for issue in self.issues if issue.level == "INFO")

        print()
        print("MUME Character Archive validation")
        print("=" * 40)
        print(f"Errors:   {error_count}")
        print(f"Warnings: {warning_count}")
        print(f"Info:     {info_count}")
        print()

        for level in ("ERROR", "WARNING", "INFO"):
            matching = [issue for issue in self.issues if issue.level == level]

            if not matching:
                continue

            print(level)
            print("-" * len(level))

            for issue in matching:
                print(f"[{issue.file}] {issue.message}")

            print()

        if error_count:
            print("Validation failed: fix ERROR items before treating the data as structurally safe.")
            return 1

        print("Validation passed: no structural errors found.")
        print("Warnings may still identify incomplete or historically ambiguous research data.")
        return 0


def clean(value: object) -> str:
    if value is None:
        return ""

    return str(value).strip()


def split_multi_id_field(value: str) -> list[str]:
    """
    Some future fields may store multiple IDs separated by semicolons.
    For now, this also safely handles ordinary single-ID fields.
    """
    return [part.strip() for part in value.split(";") if part.strip()]


def parse_iso_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def main() -> int:
    validator = Validator()
    return validator.validate()


if __name__ == "__main__":
    sys.exit(main())
