# FuturesDesk Agent Skills

Public, research-only agent skills. No connection to FuturesDesk private production systems is provided.

## Market Evidence Auditor

Audit user-supplied sportsbook price observations without using sportsbook credentials, live feeds, paid data, or placing wagers. Compare prices only when the event, market, selection, and line are identical. The included script requires only Python 3.10+ and its standard library.

Install with the agent-skills CLI:

```bash
npx skills add FUTURESDESK/futuresdesk-skills --skill market-evidence-auditor
```

Try the wholly synthetic example:

```bash
python3 skills/market-evidence-auditor/scripts/audit_snapshot.py skills/market-evidence-auditor/assets/synthetic_quotes.csv --as-of 2026-11-07T18:02:00Z
```

Read the [skill instructions](skills/market-evidence-auditor/SKILL.md). Snapshot prices do not prove live availability, independent fair value, positive expected value, or sportsbook liability.

**License:** MIT applies only to files in this public repository. It grants no rights to FuturesDesk's private code, models, databases, brand marks, subscriptions, or third-party data.

Website: https://futuresdesk.io
