"""Offline, synthetic contract tests."""

import csv
import importlib.util
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("audit_snapshot", ROOT / "skills/market-evidence-auditor/scripts/audit_snapshot.py")
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)
HEADERS = ["event_id", "market", "selection", "line", "odds_american", "source", "captured_at", "book", "jurisdiction", "source_type"]


def quote(**kwargs):
    value = dict(event_id="SYNTH-2026-11-07-A-B", market="spread", selection="A", line="+3", odds_american="-110", source="A", captured_at="2026-11-07T18:00:00Z", book="Book A", jurisdiction="UNKNOWN", source_type="SCREENSHOT")
    value.update(kwargs)
    return value


def audit(rows, **kwargs):
    with tempfile.TemporaryDirectory() as temporary:
        path = Path(temporary) / "quotes.csv"
        with path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=HEADERS)
            writer.writeheader()
            writer.writerows(rows)
        return module.audit(path, **kwargs)


class AuditTests(unittest.TestCase):
    def test_exact_line_only(self):
        r = audit([quote(), quote(source="B", book="Book B", odds_american="-115"), quote(line="+2.5", odds_american="-105")])
        self.assertEqual(r["totals"]["groups"], 2)
        group = next(g for g in r["groups"] if g["line"] == "+3")
        self.assertEqual(group["best_observed"]["odds_american"], -110)
        self.assertFalse(r["fair_value_established"] or r["execution_authority"] or r["live_quote_verified"])

    def test_duplicate_is_not_a_missing_source_failure(self):
        r = audit([quote(), quote()])
        self.assertEqual(r["totals"]["exact_duplicates_suppressed"], 1)
        self.assertEqual(r["status"], "RESEARCH_ONLY")
        self.assertIsNone(r["groups"][0]["best_observed"])

    def test_missing_timestamp_quarantine(self):
        r = audit([quote(captured_at="UNKNOWN")])
        self.assertEqual(r["status"], "HOLD_EVIDENCE_GAP")
        self.assertEqual(r["totals"]["quarantined"], 1)

    def test_timezone_required(self):
        r = audit([quote(captured_at="2026-11-07T18:00:00")])
        self.assertEqual(r["quarantined"][0]["reason"], "TIMESTAMP_TIMEZONE_REQUIRED")

    def test_skew_blocks_winner(self):
        r = audit([quote(), quote(source="B", book="Book B", captured_at="2026-11-07T18:25:00Z")])
        self.assertIn("CAPTURE_TIME_SKEW", r["groups"][0]["blocking_reasons"])
        self.assertIsNone(r["groups"][0]["best_observed"])

    def test_same_capture_conflict(self):
        r = audit([quote(), quote(odds_american="-120")])
        self.assertIn("SAME_CAPTURE_CONFLICT", r["groups"][0]["blocking_reasons"])

    def test_stale(self):
        now = datetime(2026, 11, 7, 19, tzinfo=timezone.utc)
        r = audit([quote(), quote(source="B", book="Book B")], as_of=now)
        self.assertIn("FRESHNESS_GAP", r["groups"][0]["blocking_reasons"])

    def test_invalid_line_and_odds(self):
        r = audit([quote(line="+banana"), quote(odds_american="-95")])
        self.assertEqual(r["totals"]["accepted"], 0)
        self.assertEqual(r["totals"]["quarantined"], 2)


if __name__ == "__main__":
    unittest.main()
