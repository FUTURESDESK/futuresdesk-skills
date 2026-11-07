#!/usr/bin/env python3
"""Offline, research-only audit of user-supplied American odds observations."""

import argparse
import csv
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

REQUIRED = ("event_id", "market", "selection", "line", "odds_american", "source", "captured_at")
OPTIONAL = ("book", "jurisdiction", "source_type")
SOURCE_TYPES = {"SCREENSHOT", "REPORTED", "PAGE", "API", "UNKNOWN"}


def parse_time(value):
    try:
        dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except (ValueError, AttributeError) as exc:
        raise ValueError("INVALID_TIMESTAMP") from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("TIMESTAMP_TIMEZONE_REQUIRED")
    return dt.astimezone(timezone.utc)


def normalize_line(raw, market):
    if market == "moneyline":
        if raw not in ("", "UNKNOWN"):
            raise ValueError("MONEYLINE_HAS_LINE")
        return ""
    if not raw or raw == "UNKNOWN":
        raise ValueError("LINE_REQUIRED")
    try:
        number = Decimal(raw)
    except InvalidOperation as exc:
        raise ValueError("INVALID_LINE") from exc
    if not number.is_finite():
        raise ValueError("INVALID_LINE")
    return ("+" if number > 0 else "") + format(number.normalize() if number else Decimal(0), "f")


def price(raw):
    try:
        odds = int(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("INVALID_AMERICAN_ODDS") from exc
    if abs(odds) < 100:
        raise ValueError("INVALID_AMERICAN_ODDS")
    decimal_odds = 1 + (odds / 100 if odds > 0 else 100 / abs(odds))
    return odds, round(decimal_odds, 6), round(1 / decimal_odds, 6)


def audit(path, as_of=None, max_age=10, max_skew=10):
    if max_age < 0 or max_skew < 0:
        raise ValueError("NEGATIVE_TIME_LIMIT")
    with Path(path).open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        missing = set(REQUIRED) - set(reader.fieldnames or ())
        if missing:
            raise ValueError("MISSING_COLUMNS:" + ",".join(sorted(missing)))
        raw_rows = list(reader)

    accepted, quarantine, issues, seen = [], [], [], set()
    duplicates = 0
    for row_num, raw in enumerate(raw_rows, 2):
        try:
            r = {key: (raw.get(key) or "").strip() for key in REQUIRED + OPTIONAL}
            for key in ("event_id", "market", "selection", "source", "captured_at"):
                if not r[key] or r[key] == "UNKNOWN":
                    raise ValueError("REQUIRED_FIELD_UNKNOWN:" + key)
            r["market"] = r["market"].lower()
            r["line"] = normalize_line(r["line"], r["market"])
            r["odds_american"], r["decimal_odds"], r["market_implied_probability"] = price(r["odds_american"])
            r["source_type"] = r["source_type"].upper() or "UNKNOWN"
            if r["source_type"] not in SOURCE_TYPES:
                raise ValueError("INVALID_SOURCE_TYPE")
            r["book"] = r["book"] or "UNKNOWN"
            r["jurisdiction"] = r["jurisdiction"] or "UNKNOWN"
            t = parse_time(r["captured_at"])
            r["captured_at"] = t.isoformat().replace("+00:00", "Z")
            r["row"] = row_num
            r["evidence_state"] = "RESEARCH_ONLY"
            if as_of is not None:
                age = (as_of - t).total_seconds() / 60
                r["age_minutes"] = round(age, 3)
                if age < 0:
                    issues.append({"row": row_num, "code": "FUTURE_CAPTURE"})
                elif age > max_age:
                    issues.append({"row": row_num, "code": "STALE_AT_AS_OF"})
            identity = tuple(r[k] for k in REQUIRED + OPTIONAL)
            if identity in seen:
                duplicates += 1
                issues.append({"row": row_num, "code": "EXACT_DUPLICATE_SUPPRESSED"})
                continue
            seen.add(identity)
            accepted.append(r)
        except ValueError as exc:
            quarantine.append({"row": row_num, "reason": str(exc)})

    groups_by_key = defaultdict(list)
    for r in accepted:
        groups_by_key[(r["event_id"].casefold(), r["market"], r["selection"].casefold(), r["line"])].append(r)

    groups = []
    for key, rows in sorted(groups_by_key.items()):
        times = [parse_time(r["captured_at"]) for r in rows]
        skew = (max(times) - min(times)).total_seconds() / 60
        same_capture = defaultdict(set)
        for r in rows:
            same_capture[(r["source"], r["book"], r["captured_at"])].add(r["odds_american"])
        blocked = []
        if any(len(prices) > 1 for prices in same_capture.values()):
            blocked.append("SAME_CAPTURE_CONFLICT")
        if skew > max_skew:
            blocked.append("CAPTURE_TIME_SKEW")
        if as_of is not None and any((as_of - t).total_seconds() < 0 or (as_of - t).total_seconds() > max_age * 60 for t in times):
            blocked.append("FRESHNESS_GAP")
        single_source = len({(r["source"], r["book"]) for r in rows}) < 2
        ranked = sorted(rows, key=lambda r: (-r["decimal_odds"], r["source"], r["book"]))
        best = ranked[0] if not blocked and not single_source else None
        groups.append({
            "event_id": rows[0]["event_id"], "market": rows[0]["market"],
            "selection": rows[0]["selection"], "line": rows[0]["line"],
            "status": "HOLD_EVIDENCE_GAP" if blocked else ("RESEARCH_ONLY_SINGLE_SOURCE" if single_source else "RESEARCH_ONLY_COMPARABLE"),
            "blocking_reasons": blocked, "comparison_limitations": ["SINGLE_SOURCE"] if single_source else [],
            "capture_skew_minutes": round(skew, 3),
            "best_observed": ({k: best[k] for k in ("row", "odds_american", "source", "book", "captured_at")} if best else None),
            "observations": rows,
        })

    return {
        "contract": "FD-PUBLIC-MARKET-EVIDENCE-AUDIT-v1",
        "status": "HOLD_EVIDENCE_GAP" if quarantine or any(g["blocking_reasons"] for g in groups) else "RESEARCH_ONLY",
        "execution_authority": False, "fair_value_established": False, "live_quote_verified": False,
        "totals": {"input_rows": len(raw_rows), "accepted": len(accepted), "quarantined": len(quarantine), "exact_duplicates_suppressed": duplicates, "groups": len(groups)},
        "quarantined": quarantine, "issues": issues, "groups": groups,
        "as_of_utc": as_of.isoformat().replace("+00:00", "Z") if as_of else None,
        "limitations": ["Historical observations only; no live price verification.", "Market-implied probability is not independent fair value.", "Best observed same-line price is not EV or a betting recommendation.", "No sportsbook liability or executable quote established."],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path)
    parser.add_argument("--as-of")
    parser.add_argument("--max-age-minutes", type=float, default=10)
    parser.add_argument("--max-skew-minutes", type=float, default=10)
    args = parser.parse_args()
    try:
        report = audit(args.csv, parse_time(args.as_of) if args.as_of else None, args.max_age_minutes, args.max_skew_minutes)
    except (ValueError, OSError) as exc:
        print(json.dumps({"status": "HOLD_INPUT_ERROR", "reason": str(exc)}), file=sys.stderr)
        return 2
    print(json.dumps(report, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
