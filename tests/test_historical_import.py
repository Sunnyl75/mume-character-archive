"""Meaningful regression checks for evidence identity, conflicts and public export."""
import contextlib
import csv
import importlib.util
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from import_historical_evidence import Importer, date_fields
from historical_views import build_history
import import_mudlet_whois_archive as whois


def corpus():
    return {"schema_version": "mume_historical_logs_corpus/1.0-consolidated", "records": [
        {"record_id": "log_fixture", "title": "A battle", "source_file": "battle.txt",
         "credited_observer": "Observer", "principal_characters": ["Victim"],
         "event_date": {"display": "c. 1995", "earliest": "1995-01-01", "latest": "1995-12-31"},
         "deaths": [{"character": "Victim", "evidence": "directly observed", "count": 2},
                    {"character": "Maybe", "evidence": "outcome explicitly unknown"},
                    {"entity": "Balrog", "entity_type": "mobile"}],
         "trophy_list": {"present": True, "derived_kill_evidence": [
             {"killer_character": "Observer", "victim_character": "HistoricalVictim", "minimum_kill_count": 3}]}}
    ]}


class HistoricalImportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.root = self.base / "archive"
        self.root.mkdir()
        self.input = self.base / "input"
        self.input.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def ingest(self, data, importer=None, filename="fixture.json"):
        path = self.input / filename
        path.write_text(json.dumps(data))
        imp = importer or Importer(self.root)
        self.assertTrue(imp.ingest(path, Path(filename)))
        return imp

    def test_deaths_trophies_and_uncertainty_stay_distinct(self):
        imp = self.ingest(corpus())
        imp.finish()
        events = imp.tables["historical_events"]
        self.assertEqual([(e["event_type"], e["count"]) for e in events], [("death", "2"), ("trophy", "3")])
        self.assertNotIn("Maybe", [e["character_name"] for e in events])
        self.assertNotIn("Balrog", [c["name"] for c in imp.tables["characters"]])
        imp.write_tables(self.root)
        public = build_history(self.root)
        victim = next(c for c in imp.tables["characters"] if c["name"] == "HistoricalVictim")
        self.assertNotIn(victim["character_id"], public)  # trophy victim did not attend battle
        self.assertTrue(any(x["kind"] == "uncertain_death" for x in imp.review))

    def test_reimport_has_no_net_changes_and_keeps_manual_decision(self):
        imp = self.ingest(corpus())
        self.ingest({"schema_version": "mume_whois_queue_evidence/0.1", "player_id": "pOwner", "characters": [
            {"character_name": "Observer", "same_player_as": "pOwner", "evidence_confidence": "high"}]}, imp, "links.json")
        imp.finish()
        imp.tables["player_character_links"][0]["status"] = "rejected"
        imp.write_tables(self.root)
        again = self.ingest(corpus())
        self.ingest(json.loads((self.input / "links.json").read_text()), again, "links.json")
        again.finish()
        self.assertFalse(again.changes)
        self.assertEqual(again.tables["player_character_links"][0]["status"], "rejected")

    def test_links_need_review_and_conflicts_never_silently_replace(self):
        imp = Importer(self.root, accept_links=True)
        payload = {"schema_version": "mume_player_character_evidence/0.1", "players": [
            {"pName": "pOne", "characters_as_written": ["Shared"], "confidence": "high", "real_name_private": "PRIVATE_SENTINEL"},
            {"pName": "pTwo", "characters_as_written": ["Shared"], "confidence": "high"}]}
        self.ingest(payload, imp)
        imp.finish()
        self.assertEqual({r["status"] for r in imp.tables["player_character_links"]}, {"needs_review"})
        self.assertNotIn("PRIVATE_SENTINEL", json.dumps(imp.tables["players"]))
        self.assertIn("PRIVATE_SENTINEL", json.dumps(imp.tables["evidence"]))

    def test_deduplicate_queue_against_captures_but_keep_new_link(self):
        imp = Importer(self.root)
        imp.captured.add("observer")
        self.ingest({"schema_version": "mume_whois_queue_evidence/0.1", "player_id": "pOwner", "characters": [
            {"character_name": "Observer", "evidence_confidence": "high"}]}, imp)
        self.assertEqual(len(imp.tables["player_character_links"]), 1)
        self.assertFalse(imp.tables["whois_queue"])
        self.assertEqual(imp.tables["player_character_links"][0]["status"], "needs_review")

    def test_alternative_dates_and_unmatched_log_references(self):
        dates = date_fields({"preferred": "1996-10-05", "alternative": "1994-10-05"})
        self.assertEqual(dates["date_confidence"], "unknown")
        self.assertFalse(dates["date_range_start"])
        imp = self.ingest({"schema_version": "deck_of_chars_log_list/0.4", "entries": [
            {"source_entry_id": "missing", "logical_log_id": "unknown_log", "display_title": "Unknown"}]})
        imp.finish()
        self.assertEqual(imp.tables["historical_log_index"][0]["log_id"], "")
        self.assertEqual(imp.tables["historical_log_index"][0]["source_log_id"], "unknown_log")

    def test_public_export_excludes_private_notes_and_unsafe_links(self):
        imp = self.ingest(corpus())
        imp.tables["logs"][0]["source_url"] = "javascript:alert(1)"
        imp.tables["logs"][0]["notes"] = "PRIVATE_SENTINEL"
        imp.tables["historical_events"][0]["observation_status"] = "PRIVATE_SENTINEL"
        imp.write_tables(self.root)
        text = json.dumps(build_history(self.root))
        self.assertNotIn("PRIVATE_SENTINEL", text)
        self.assertNotIn("javascript:", text)

    def test_whois_import_reuses_historical_character_id(self):
        imp = self.ingest(corpus())
        before = next(c["character_id"] for c in imp.tables["characters"] if c["name"] == "Observer")
        archive = {"captures": [{"query_name": "Observer", "captured_at": "2026-11-05", "raw_text": "Observer the warrior",
                               "parsed": {"character_name": "Observer"}}],
                   "records": {"observer": {"latest": {"character_name": "Observer", "class": "Warrior"}}}}
        whois.import_captures(archive, imp.tables["characters"], [], imp.tables["whois_queue"])
        self.assertEqual([c["character_id"] for c in imp.tables["characters"] if c["name"] == "Observer"], [before])

    def test_apply_validates_and_rolls_back_failed_replacement(self):
        shutil.copytree(ROOT / "data/working", self.root / "data/working")
        imp = self.ingest(corpus())
        imp.finish()
        old = {p.name: p.read_bytes() for p in (self.root / "data/working").glob("*.csv")}
        original_replace = Path.replace
        calls = 0
        def fail_second(path, target):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("simulated interrupted write")
            return original_replace(path, target)
        with patch.object(Path, "replace", fail_second), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(OSError):
                imp.apply(self.input, "rollback_test")
        self.assertEqual(old, {p.name: p.read_bytes() for p in (self.root / "data/working").glob("*.csv")})
        self.assertFalse((self.root / "data/incoming/historical/rollback_test").exists())
        with contextlib.redirect_stdout(io.StringIO()):
            retained = imp.apply(self.input, "success_test")
        self.assertEqual(json.loads((retained / "sources/fixture.json").read_text()), corpus())


if __name__ == "__main__":
    unittest.main()
