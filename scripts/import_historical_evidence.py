#!/usr/bin/env python3
"""Preview/import structured historical research; no network or publication.

Supports the July research bundle, standalone corpus, website player evidence,
same-player queue candidates, and Deck log index JSON. Raw text is preserved;
this is an importer for reviewed extractions, not a gameplay-log parser.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import date
import hashlib
import json
from pathlib import Path
import re
import shutil
import tempfile
from historical_review import groups_for, level
from source_review import apply_reviewed, saved_facts

ROOT = Path(__file__).resolve().parents[1]
VERSION = "historical-import/1"
FIELDS = {
    "sources": "source_id,title,source_type,url,date_found,reliability,notes",
    "characters": "character_id,name,race,class,level,status,first_seen,last_seen,whois_checked,duplicate_count,notes",
    "players": "primary_source_id,player_id,main_handle,real_name,known_by,notes",
    "player_character_links": "link_id,player_id,character_id,character_name,main_handle,link_type,status,confidence,primary_evidence_id,notes",
    "evidence": "evidence_id,source_id,evidence_type,subject_type,subject_id_or_name,claim,raw_text,location_in_source,date_observed,date_range_start,date_range_end,date_confidence,confidence,notes",
    "logs": "log_id,title,filename,date_exact,date_range_start,date_range_end,date_confidence,date_basis,notes,source_id,source_url,display_date",
    "log_appearances": "appearance_id,log_id,character_id,character_name,line_excerpt,event_type,date_range_start,date_range_end,date_confidence,confidence,notes,evidence_id",
    "historical_events": "event_id,log_id,source_id,event_type,character_id,character_name,other_character_id,other_character_name,count,date_range_start,date_range_end,display_date,date_confidence,confidence,evidence_id,location,observation_status,review_status",
    "historical_log_index": "entry_id,log_id,source_log_id,title,display_date,url,original_url,source_id,recovery_status",
    "whois_queue": "character_name,character_id,already_checked,priority,notes",
}
IDS = {"sources": "source_id", "characters": "character_id", "players": "player_id",
       "player_character_links": "link_id", "evidence": "evidence_id", "logs": "log_id",
       "log_appearances": "appearance_id", "historical_events": "event_id",
       "historical_log_index": "entry_id", "whois_queue": "character_name"}


def clean(value):
    return str(value or "").strip()


def serial(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def ident(kind, *parts):
    return kind + "_" + hashlib.sha256(serial(parts).encode()).hexdigest()[:20]


def name(value):
    value = clean(value)
    return value if re.fullmatch(r"[^\W\d_][^\W_'-]*(?:['-][^\W_]+)*", value, re.UNICODE) else ""


def confidence(value):
    return level(value)


def date_fields(value):
    value = value if isinstance(value, dict) else {"display": clean(value)}
    start, end = clean(value.get("earliest")), clean(value.get("latest"))
    # A preferred date with competing alternatives is not an exact date.
    display = clean(value.get("display") or value.get("preferred_display") or value.get("preferred"))
    if value.get("alternative"):
        display = f"{display} (alternative: {value['alternative']})"
    for bound in (start, end):
        if bound:
            date.fromisoformat(bound)
    if start and end and start > end:
        raise ValueError("Historical date range is reversed")
    return {"date_range_start": start, "date_range_end": end,
            "display_date": display or (f"{start}–{end}" if start or end else "Date uncertain"),
            "date_confidence": "exact" if start and start == end else "bounded" if start or end else "unknown"}


class Importer:
    def __init__(self, root, *, accept_links=False, player_map=None):
        self.root = Path(root)
        self.accept_links = accept_links
        self.player_map = player_map or {}
        self.tables, self.headers, self.indexes = {}, {}, {}
        self.changes = Counter()
        self.review = []
        self.inputs = []
        self.original = {}
        for table, fields in FIELDS.items():
            path = self.root / "data/working" / (table + ".csv")
            if path.exists():
                with path.open(encoding="utf-8-sig", newline="") as f:
                    reader = csv.DictReader(f)
                    self.headers[table] = list(reader.fieldnames or [])
                    self.tables[table] = list(reader)
            else:
                self.headers[table], self.tables[table] = [], []
            self.headers[table] += [f for f in fields.split(",") if f not in self.headers[table]]
            self.indexes[table] = {clean(r.get(IDS[table])).casefold(): r for r in self.tables[table]}
            self.original[table] = {key: dict(row) for key, row in self.indexes[table].items()}
        self.characters = {}
        for row in self.tables["characters"]:
            self.characters.setdefault(clean(row.get("name")).casefold(), []).append(row)
        self.captured = set()
        path = self.root / "data/working/whois_records.csv"
        if path.exists():
            with path.open(encoding="utf-8-sig", newline="") as f:
                self.captured = {clean(r.get("character_name")).casefold() for r in csv.DictReader(f)}

    def put(self, table, row):
        key = clean(row[IDS[table]]).casefold()
        current = self.indexes[table].get(key)
        if current is None:
            current = {f: "" for f in self.headers[table]}
            self.tables[table].append(current)
            self.indexes[table][key] = current
            self.changes[table + ": added"] += 1
        elif all(clean(current.get(k)) == clean(v) for k, v in row.items()):
            return current
        else:
            self.changes[table + ": updated"] += 1
        current.update({k: clean(v) for k, v in row.items()})
        return current

    def character(self, value):
        value = name(value)
        if not value:
            return None
        found = self.characters.get(value.casefold(), [])
        if len(found) > 1:
            self.review.append({"kind": "ambiguous_character", "character": value})
            return None
        if found:
            return found[0]
        row = self.put("characters", {"character_id": ident("char_hist", value.casefold()), "name": value,
                                     "notes": "Historical source attestation; current status unknown."})
        self.characters[value.casefold()] = [row]
        return row

    def queue(self, char, evidence_id):
        if not char:
            return
        key = char["name"].casefold()
        if key in self.indexes["whois_queue"] or key in self.captured:
            return
        if clean(char.get("whois_checked")).casefold() in {"true", "yes", "1"}:
            return
        self.put("whois_queue", {"character_name": char["name"], "character_id": char["character_id"],
                                "already_checked": "false", "priority": "normal", "notes": f"Historical evidence: {evidence_id}"})

    def evidence(self, source, location, kind, subject, raw, dates=None):
        dates = dates or date_fields({})
        eid = ident("evidence_hist", source, location, kind)
        self.put("evidence", {"evidence_id": eid, "source_id": source, "evidence_type": kind,
                             "subject_type": "character", "subject_id_or_name": subject,
                             "claim": f"{kind}: {subject}", "raw_text": serial(raw),
                             "location_in_source": location, "date_range_start": dates["date_range_start"],
                             "date_range_end": dates["date_range_end"], "date_confidence": dates["date_confidence"],
                             "confidence": confidence(raw.get("confidence") or raw.get("evidence_confidence")) if isinstance(raw, dict) else "medium",
                             "notes": VERSION + "; source-derived evidence, not timeless character truth"})
        return eid

    def player(self, handle, source):
        handle = clean(handle)
        if not handle:
            return None
        mapped = self.player_map.get(handle)
        if mapped:
            row = self.indexes["players"].get(mapped.casefold())
            if not row:
                raise ValueError(f"Player mapping target does not exist: {mapped}")
            return row
        # Only exact public handle/ID matches. Never infer an owner from shared characters.
        matches = [r for r in self.tables["players"] if handle.casefold() in {
            clean(r.get("player_id")).casefold(), clean(r.get("main_handle")).casefold(),
            clean(r.get("known_by")).casefold()}]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            self.review.append({"kind": "ambiguous_player", "player": handle})
            return None
        return self.put("players", {"player_id": ident("player_hist", handle.casefold()),
                                    "main_handle": handle, "known_by": handle, "primary_source_id": source,
                                    "notes": "Public pName from historical evidence; identity requires review."})

    def link(self, source, location, character_name, handle, raw):
        char, player = self.character(character_name), self.player(handle, source)
        if not char or not player:
            return
        eid = self.evidence(source, location, "player_character_association", char["name"], raw)
        conflicts = [r for r in self.tables["player_character_links"]
                     if r.get("character_id") == char["character_id"] and r.get("status") == "accepted"
                     and r.get("player_id") != player["player_id"]]
        status = "accepted" if self.accept_links and not conflicts and confidence(raw.get("confidence") or raw.get("evidence_confidence")) == "high" else "needs_review"
        lid = ident("link_hist", eid)
        old = self.indexes["player_character_links"].get(lid)
        if old and old.get("status") in {"accepted", "rejected", "disputed"}:
            status = old["status"]  # Preserve a later human decision on reimport.
        self.put("player_character_links", {"link_id": lid, "player_id": player["player_id"],
                 "character_id": char["character_id"], "character_name": char["name"],
                 "main_handle": player["main_handle"], "link_type": "listed_same_player", "status": status,
                 "confidence": confidence(raw.get("confidence") or raw.get("evidence_confidence")),
                 "primary_evidence_id": eid, "notes": "Historical assertion; " + ("conflicting accepted owner" if conflicts else "exact-name match; no identity merge")})
        if status == "needs_review":
            self.review.append({"kind": "player_link", "link_id": lid, "character": char["name"],
                                "proposed_player": player["main_handle"], "conflict": bool(conflicts)})
        self.queue(char, eid)

    def appearance(self, source, logid, charname, location, raw, dates, kind="appearance"):
        char = self.character(charname)
        if not char:
            return
        eid = self.evidence(source, location, kind, char["name"], raw, dates)
        self.put("log_appearances", {"appearance_id": ident("appearance_hist", eid), "log_id": logid,
                 "character_id": char["character_id"], "character_name": char["name"],
                 "line_excerpt": "", "event_type": kind, "date_range_start": dates["date_range_start"],
                 "date_range_end": dates["date_range_end"], "date_confidence": dates["date_confidence"],
                 "confidence": "medium", "evidence_id": eid, "notes": "Structured extraction; raw source retained, not a verbatim line citation."})
        self.queue(char, eid)

    def event(self, source, logid, location, kind, charname, other, count, raw, dates):
        char, counterpart = self.character(charname), self.character(other) if other else None
        if not char or (other and not counterpart):
            self.review.append({"kind": "unresolved_event", "log_id": logid, "location": location})
            return
        if type(count) is not int or count < 1:
            raise ValueError(f"Invalid event count in {logid}/{location}")
        eid = self.evidence(source, location, kind, char["name"], raw, dates)
        event_id = ident("event_hist", eid)
        old = self.indexes['historical_events'].get(event_id)
        review_status = (old.get('review_status') or 'accepted') if old else 'needs_review'
        self.put("historical_events", {"event_id": event_id, "log_id": logid, "source_id": source,
                 "event_type": kind, "character_id": char["character_id"], "character_name": char["name"],
                 "other_character_id": counterpart["character_id"] if counterpart else "",
                 "other_character_name": counterpart["name"] if counterpart else "", "count": count,
                 **dates, "confidence": confidence(raw.get("confidence")), "evidence_id": eid,
                 "location": clean(raw.get("location")), "observation_status": clean(raw.get("evidence") or "structured extraction"),
                 "review_status": review_status})
        self.queue(char, eid)
        self.queue(counterpart, eid)

    def corpus(self, source, data):
        records = data.get("records")
        if not isinstance(records, list):
            raise ValueError("Historical corpus records must be a list")
        for rec in records:
            logid = clean(rec["record_id"])
            dates = date_fields(rec.get("event_date"))
            self.put("logs", {"log_id": logid, "title": clean(rec.get("title")),
                     "filename": clean(rec.get("source_file")), "source_id": source,
                     **({"source_url": clean(rec["source_url"])} if rec.get("source_url") else {}),
                     "date_exact": dates["date_range_start"] if dates["date_confidence"] == "exact" else "",
                     **dates, "date_basis": serial(rec.get("event_date", {})),
                     "notes": "Historical structured extraction; alternative dates preserved in date_basis."})
            self.evidence(source, logid, "logical_log", "", rec, dates)
            names = set()
            def collect(value):
                if isinstance(value, str) and name(value):
                    names.add(value)
                elif isinstance(value, list):
                    for item in value:
                        collect(item)
                elif isinstance(value, dict):
                    for item in value.values():
                        collect(item)
            for key in ("credited_observer", "credited_observers", "participants_named", "participants", "principal_characters",
                        "named_group", "named_free_people_observed", "named_darkside_observed"):
                collect(rec.get(key))
            for key in ("character_snapshots", "key_character_snapshots"):
                for snap in rec.get(key, []):
                    collect(snap.get("character"))
            for charname in sorted(names):
                self.appearance(source, logid, charname, logid + "/appearance/" + charname.casefold(), {"character": charname}, dates)
            deaths = list(rec.get("deaths", []))
            deaths += [{"character": n, "evidence": "named observed death in structured extraction"}
                       for n in rec.get("observed_deaths", {}).get("named", [])]
            for i, death in enumerate(deaths):
                if death.get("entity_type") == "mobile":
                    continue
                basis = clean(death.get("evidence")).casefold()
                if any(s in basis for s in ("unknown", "uncertain", "not observed")):
                    self.review.append({"kind": "uncertain_death", "log_id": logid, "raw": death})
                    continue
                self.event(source, logid, f"{logid}/death/{i}", "death", death.get("character"), "", death.get("count", 1), death, dates)
            trophy = rec.get("trophy_list", {})
            if trophy.get("present"):
                entries = trophy.get("derived_kill_evidence", [])
                if not entries and trophy.get("player_entries"):
                    self.review.append({"kind": "trophy_owner_requires_review", "log_id": logid})
                for i, entry in enumerate(entries):
                    entry = {**entry, 'source_context': {'trophy_owner': trophy.get('owner', ''),
                                                         'observer': rec.get('credited_observer', '')}}
                    self.event(source, logid, f"{logid}/trophy/{i}", "trophy", entry.get("killer_character"),
                               entry.get("victim_character"), entry.get("minimum_kill_count"), entry, dates)

    def ingest(self, path, relative):
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return False
        schema = clean(data.get("schema_version"))
        supported = ("mume_historical_logs_corpus/", "mume_whois_queue_evidence/", "mume_player_character_evidence/", "deck_of_chars_log_list/")
        if not schema.startswith(supported):
            return False
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        source = ident("source_hist", str(relative), digest)
        self.inputs.append({"path": str(relative), "sha256": digest, "schema": schema, "source_id": source})
        self.put("sources", {"source_id": source, "title": path.name, "source_type": "historical_research",
                 "url": clean(data.get("source_capture_url")), "reliability": "reviewed_structured_extraction",
                 "notes": f"{VERSION}; retained input {relative}; SHA256 {digest}"})
        if schema.startswith("mume_historical_logs_corpus/"):
            self.corpus(source, data)
        elif schema.startswith("mume_whois_queue_evidence/"):
            entries = list(data.get("characters", []))
            if data.get("additional_website_candidate"):
                entries.append(data["additional_website_candidate"])
            for i, entry in enumerate(entries):
                entry = {**entry, 'source_context': {'evidence_type': data.get('evidence_type', ''),
                                                    'source_capture_url': data.get('source_capture_url', '')}}
                self.link(source, f"characters/{i}", entry.get("character_name"), entry.get("same_player_as") or data.get("player_id"), entry)
        elif schema.startswith("mume_player_character_evidence/"):
            for i, player in enumerate(data.get("players", [])):
                for j, charname in enumerate(player.get("characters_as_written", [])):
                    self.link(source, f"players/{i}/characters/{j}", charname, player.get("pName") or player.get("player_id"), player)
        else:
            for entry in data.get("entries", []):
                lid = clean(entry.get("logical_log_id"))
                self.put("historical_log_index", {"entry_id": ident("logindex_hist", source, entry["source_entry_id"]),
                         "log_id": lid, "title": clean(entry.get("display_title")), "display_date": clean(entry.get("display_date")),
                         "url": clean(entry.get("link_url")), "original_url": clean(entry.get("original_url")),
                         "source_id": source, "recovery_status": clean(entry.get("content_recovery_status"))})
        return True

    def finish(self):
        # Detect conflicting assertions across the whole input, not just import order.
        targets = {}
        for link in self.tables["player_character_links"]:
            if link.get("status") in {"accepted", "needs_review"}:
                targets.setdefault(link["character_id"], set()).add(link["player_id"])
        for link in self.tables["player_character_links"]:
            if len(targets.get(link["character_id"], set())) > 1 and link["link_id"].startswith("link_hist_"):
                old = self.original["player_character_links"].get(link["link_id"].casefold(), {})
                if old.get("status") not in {"accepted", "rejected", "disputed"}:
                    self.put("player_character_links", {"link_id": link["link_id"], "status": "needs_review"})
                    self.review.append({"kind": "conflicting_player_assertions", "link_id": link["link_id"], "character": link["character_name"]})
        # Curated index links enrich the log but never change its event date or ownership.
        for entry in self.tables["historical_log_index"]:
            if entry["log_id"] and entry["log_id"].casefold() not in self.indexes["logs"]:
                self.review.append({"kind": "unmatched_log_reference", "entry_id": entry["entry_id"], "source_log_id": entry["log_id"]})
                self.put("historical_log_index", {"entry_id": entry["entry_id"], "source_log_id": entry["log_id"], "log_id": ""})
            log = self.indexes["logs"].get(entry["log_id"].casefold())
            if log and not log.get("source_url"):
                self.put("logs", {"log_id": log["log_id"], "source_url": entry["url"]})
        apply_reviewed(self.root, self.tables)
        self.changes.clear()
        for table, current in self.indexes.items():
            for key, row in current.items():
                old = self.original[table].get(key)
                if old is None:
                    self.changes[table + ": added"] += 1
                elif any(clean(row.get(k)) != clean(old.get(k)) for k in set(row) | set(old)):
                    self.changes[table + ": updated"] += 1

    def write_tables(self, destination):
        for table, rows in self.tables.items():
            path = destination / "data/working" / (table + ".csv")
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=self.headers[table])
                writer.writeheader()
                writer.writerows(rows)

    def preview_details(self):
        """Describe the final net change, with evidence references, without writing."""
        evidence = self.indexes["evidence"]
        by_character, by_player, by_log = {}, {}, {}

        def associate(index, key, eid):
            if key and eid:
                index.setdefault(clean(key).casefold(), set()).add(eid)

        for row in self.tables["evidence"]:
            associate(by_character, row.get("subject_id_or_name"), row["evidence_id"])
            if row.get("evidence_type") == "logical_log":
                associate(by_log, row.get("location_in_source"), row["evidence_id"])
        for row in self.tables["player_character_links"]:
            associate(by_player, row.get("player_id"), row.get("primary_evidence_id"))
        for rows in (self.tables["log_appearances"], self.tables["historical_events"]):
            for row in rows:
                associate(by_character, row.get("character_id"), row.get("evidence_id"))

        records, referenced = [], set()
        for table, current in self.indexes.items():
            for key, row in current.items():
                old = self.original[table].get(key)
                fields = [field for field in self.headers[table]
                          if clean(row.get(field)) != clean((old or {}).get(field))]
                if old is not None and not fields:
                    continue
                eids = set()
                for column in ("evidence_id", "primary_evidence_id"):
                    if row.get(column):
                        eids.add(row[column])
                if table == "characters":
                    eids.update(by_character.get(key, set()))
                    eids.update(by_character.get(clean(row.get("name")).casefold(), set()))
                if table == "players":
                    eids.update(by_player.get(key, set()))
                if table == "logs":
                    eids.update(by_log.get(key, set()))
                if table == "whois_queue":
                    eids.update(by_character.get(clean(row.get("character_name")).casefold(), set()))
                    eids.update(re.findall(r"evidence_hist_[a-f0-9]{20}", row.get("notes", "")))
                source_ids = {row[column] for column in ("source_id", "primary_source_id") if row.get(column)}
                for eid in eids:
                    source_id = evidence.get(eid.casefold(), {}).get("source_id")
                    if source_id:
                        source_ids.add(source_id)
                if table == "sources":
                    source_ids.add(row["source_id"])
                records.append({"key": table + ":" + row[IDS[table]], "table": table,
                                "id": row[IDS[table]], "action": "added" if old is None else "updated",
                                "before": dict(old) if old is not None else None, "after": dict(row),
                                "changed_fields": fields, "evidence_ids": sorted(eids),
                                "source_ids": sorted(source_ids)})
                referenced.update(eids)
        source_context = {row["source_id"]: dict(row) for row in self.tables["sources"]}
        for item in self.inputs:
            source_context[item["source_id"]]["input_file"] = item["path"]
        claim_review = groups_for(self.tables['player_character_links'], self.tables['historical_events'],
                                  self.tables['evidence'], self.tables['logs'], self.tables['sources'],
                                  selected_keys={r['key'] for r in records}, reviewed=saved_facts(self.root))
        assessments = {m['record_key']: m['assessment'] for g in claim_review['groups'] for m in g['members']}
        for record in records:
            if record['key'] in assessments:
                record['assessment'] = assessments[record['key']]
        logical_logs = {}
        for ev in self.tables['evidence']:
            if ev.get('evidence_type') == 'logical_log':
                try:
                    logical_logs[ev['location_in_source']] = json.loads(ev['raw_text'])
                except (ValueError, TypeError):
                    pass
        for logid, logical in logical_logs.items():
            if not logical.get('source_url'):
                logical['source_url'] = self.indexes['logs'].get(logid.casefold(), {}).get('source_url', '')
        claim_review['summary']['routine_records'] = len(records) - len(assessments)
        return {"preview_schema": "historical-preview/2", "records": records, 'claim_review': claim_review,
                'log_context': logical_logs,
                'source_fact_context': {name: self.tables[name] for name in
                                        ('player_character_links', 'historical_events', 'evidence', 'logs', 'sources', 'log_appearances')},
                "evidence_context": {eid: dict(evidence[eid.casefold()]) for eid in sorted(referenced)
                                     if eid.casefold() in evidence}, "source_context": source_context}

    def apply(self, input_path, session):
        """Stage and validate before replacing any canonical table; rollback on failure."""
        import validate_data
        with tempfile.TemporaryDirectory(prefix="historical-stage-", dir=self.root) as temp:
            stage = Path(temp)
            shutil.copytree(self.root / "data/working", stage / "data/working")
            self.write_tables(stage)
            previous = validate_data.WORKING_DIR
            try:
                validate_data.WORKING_DIR = stage / "data/working"
                validator = validate_data.Validator()
                validator.validate()
                if any(i.level == "ERROR" for i in validator.issues):
                    raise ValueError("Staged archive validation failed; no archive files changed")
            finally:
                validate_data.WORKING_DIR = previous
            incoming = self.root / "data/incoming/historical" / session
            if incoming.exists():
                # Session is an immutable input checkpoint, never overwrite another import.
                manifest = json.loads((incoming / "import-manifest.json").read_text())
                if manifest["inputs"] != self.inputs:
                    raise ValueError("Session already exists with different inputs; choose a new --session")
            else:
                retained = stage / "incoming"
                if input_path.is_dir():
                    shutil.copytree(input_path, retained / "sources")
                else:
                    (retained / "sources").mkdir(parents=True)
                    shutil.copy2(input_path, retained / "sources" / input_path.name)
                (retained / "import-manifest.json").write_text(serial({"version": VERSION, "inputs": self.inputs}) + "\n")
            written, originals = [], {}
            try:
                for table in self.tables:
                    dest = self.root / "data/working" / (table + ".csv")
                    originals[dest] = dest.read_bytes() if dest.exists() else None
                    written.append(dest)
                    (stage / "data/working" / (table + ".csv")).replace(dest)
                if not incoming.exists():
                    incoming.parent.mkdir(parents=True, exist_ok=True)
                    (stage / "incoming").replace(incoming)
            except BaseException:
                for dest in reversed(written):
                    if originals[dest] is None:
                        dest.unlink(missing_ok=True)
                    else:
                        dest.write_bytes(originals[dest])
                raise
        return incoming


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Extracted bundle directory or supported JSON file")
    parser.add_argument("--archive-root", type=Path, default=ROOT)
    parser.add_argument("--session", default="", help="Immutable input checkpoint name")
    parser.add_argument("--apply", action="store_true", help="Write after staging and validation; default is preview")
    parser.add_argument("--accept-links", action="store_true", help="Accept high-confidence links only where no accepted owner conflicts")
    parser.add_argument("--player-map", type=Path, help="JSON object mapping source pNames to existing archive player IDs")
    parser.add_argument("--report", type=Path, help="Optional JSON preview/report path (contains private research details)")
    args = parser.parse_args()
    path = args.input.expanduser().resolve(strict=True)
    root = args.archive_root.expanduser().resolve(strict=True)
    mapping = json.loads(args.player_map.read_text()) if args.player_map else {}
    importer = Importer(root, accept_links=args.accept_links, player_map=mapping)
    paths = sorted(path.rglob("*.json")) if path.is_dir() else [path]
    for item in paths:
        # Legacy/reference copies are retained as raw inputs, never imported twice.
        relative = item.relative_to(path) if path.is_dir() else Path(item.name)
        if "legacy" in relative.parts:
            continue
        importer.ingest(item, relative)
    if not importer.inputs:
        raise ValueError("No supported historical JSON inputs found")
    importer.finish()
    session = args.session or ident("research", importer.inputs)
    if not re.fullmatch(r"[A-Za-z0-9_-]+", session):
        raise ValueError("Session must contain only letters, digits, underscores and hyphens")
    if path == root or root in path.parents:
        raise ValueError("Use an input outside the archive repository to avoid recursive source copies")
    result = {"version": VERSION, "session": session, "applied": args.apply, "inputs": importer.inputs,
              "changes": dict(importer.changes), "review": importer.review}
    result.update(importer.preview_details())
    if args.apply:
        result["retained_inputs"] = str(importer.apply(path, session))
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print("Historical import " + ("applied" if args.apply else "preview — no archive files changed"))
    for key, count in sorted(importer.changes.items()):
        print(f"  {key}: {count}")
    print(f"  Review items: {len(importer.review)}")
    print("Rebuild the queue and Deck after applying. This command never publishes.")
    return result


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise SystemExit(f"Historical import stopped: {exc}")
