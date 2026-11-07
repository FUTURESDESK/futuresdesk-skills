---
name: market-evidence-auditor
description: Audit user-supplied sportsbook odds screenshots, copied tables or CSV price snapshots for provenance, exact-line comparability, duplicate quotes, conflicts and capture-time freshness. Use for sports-market research evidence QA only, not live offers, fair-value claims or wagering.
---

# Market Evidence Auditor

Create a source-preserving, **research-only** audit of sportsbook price observations supplied by the user.

## Boundaries

- Do not fetch odds, scrape sites, authenticate, make network calls, transmit data, place wagers, publish content, schedule work or access production systems.
- Never infer unknown event identity, sportsbook, market, line, price, jurisdiction or timestamp. Quarantine missing required evidence instead.
- A screenshot or user-reported quote is not a verified live executable price. Better displayed odds do not establish positive expected value, independent fair probability or sportsbook liability.
- Compare only identical `event_id + market + selection + line`. A spread at `+3` is not directly comparable to `+2.5`.
- Do not conflate bet percentages, handle percentages, featured-parlay placements or actual liability.

## Extract and audit

Transcribe supplied screenshots carefully into CSV. Verify both the market header and the selection/price pairing. Keep licensed screenshots and private input files out of public repositories.

Required CSV headers: `event_id,market,selection,line,odds_american,source,captured_at`.

Optional headers: `book,jurisdiction,source_type` (`SCREENSHOT`, `REPORTED`, `PAGE`, `API`, or `UNKNOWN`).

- `event_id`: unambiguous event/date from user evidence, never a guessed fixture.
- `line`: signed handicap or total; blank only for moneyline.
- `odds_american`: integer American odds, e.g. `-110`, `+145`.
- `source`: where this specific quote came from, such as `Unabated Best Line screenshot`. Preserve underlying book as `UNKNOWN` if not displayed.
- `captured_at`: ISO 8601 with explicit timezone (`Z` or `-08:00`), not an assumed time.
- `jurisdiction`: optional research metadata, never an admission blocker.

Run the deterministic, offline checker from the repository root:

```bash
python3 skills/market-evidence-auditor/scripts/audit_snapshot.py input.csv \
  --as-of 2026-11-07T18:02:00Z --max-age-minutes 10 --max-skew-minutes 10
```

Omit `--as-of` for a historical audit when no independently established comparison clock exists; do not label the data current. The script prints JSON, including quarantined rows, issues and exact-line groups. `best_observed` means a historical price comparison only; it is not a recommendation. When capture times diverge, same-capture quotes conflict, or a fresh as-of gate fails, the affected group must return `HOLD_EVIDENCE_GAP` with no winner.

## Present the result

1. Show capture window, sources and number of input/accepted/quarantined/duplicate rows.
2. Show exact-line comparable prices with original source, book (or `UNKNOWN`), line, odds and timestamp.
3. Distinguish a valid single-source observation from conflicting or stale evidence.
4. State explicitly that live execution, fair value, EV and sportsbook liability are **not established**.
5. Name the next independent projection or fresh-quote check only if the user separately asks for betting analysis.

Never route a research result directly into wagering or autonomous publication.
