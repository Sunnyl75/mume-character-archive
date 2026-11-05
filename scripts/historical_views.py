"""Public historical views. Only explicitly selected fields leave the archive."""
import csv
from collections import defaultdict
from urllib.parse import urlsplit
from source_review import saved_facts


def rows(root, table):
    path = root / "data/working" / (table + ".csv")
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def public_url(value):
    try:
        url = urlsplit(value or "")
        return value if url.scheme in {"http", "https"} and url.hostname and not url.username and not url.password else ""
    except ValueError:
        return ""


def build_history(root):
    reviewed = saved_facts(root)
    logs = {r["log_id"]: r for r in rows(root, "logs")}
    result = defaultdict(lambda: {"logs": [], "deaths": [], "trophies": []})
    seen = set()

    def reference(logid):
        log = logs.get(logid, {})
        return {"logId": logid, "title": log.get("title") or "Historical log",
                "date": log.get("display_date") or log.get("date_exact") or "Date uncertain",
                "url": public_url(log.get("source_url"))}

    def add_log(cid, logid):
        if cid and (cid, logid) not in seen:
            seen.add((cid, logid))
            result[cid]["logs"].append(reference(logid))

    for row in rows(root, "log_appearances"):
        add_log(row.get("character_id"), row["log_id"])
    for row in rows(root, "historical_events"):
        if row.get('review_status') and row['review_status'] != 'accepted':
            continue
        cid = row.get("character_id")
        if not cid:
            continue
        try:
            count = int(row["count"])
            if count < 1:
                continue
        except (ValueError, KeyError):
            continue
        basis = row.get("observation_status", "").casefold()
        observation = ("recovered summary" if "recovered summary" in basis else
                       "directly observed" if "directly observed" in basis else "reported in source extraction")
        item = {**reference(row["log_id"]), "id": row["event_id"], "count": count,
                "confidence": row.get("confidence", "unknown"),
                "observation": observation}
        fact = reviewed.get('historical_events:' + row['event_id'], {})
        if fact.get('citation', {}).get('quote'):
            item['observation'] = 'reviewed against source'
        details = [{'kind': f['kind'], 'value': f['value'], 'confidence': f['confidence']}
                   for f in reviewed.values() if f['status']=='accepted' and f['log_id']==row['log_id']
                   and f['kind'] in {'observer', 'attacker', 'killer', 'location'}
                   and (f.get('about')=='historical_events:' + row['event_id'] or
                        (f['kind']=='observer' and not f.get('about')))]
        if details: item['details'] = details
        # Export only explicitly accepted role/location fields; raw claims,
        # quotations, private review notes and player metadata stay private.
        if row.get("event_type") == "death":
            result[cid]["deaths"].append(item)
            add_log(cid, row["log_id"])
        elif row.get("event_type") == "trophy":
            result[cid]["trophies"].append({**item, "victim": row.get("other_character_name", ""),
                                            "victimId": row.get("other_character_id", "")})
            # A trophy victim is not added as a participant in this log.
    return dict(result)
