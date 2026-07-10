# REAL Accumulation Protocol

This protocol explains how to accumulate explicit-verified REAL evidence for Fund Flow Monitor without turning collection success into analytical evidence by default.

The project remains a Streamlit + CSV-first MVP. The protocol is manual, bounded and local. It does not add a scheduler, daemon, background service, database type, provider fallback, trading function or future-oriented model.

## Core Principle

A successful collector run is only an operational event. It becomes qualified acquisition evidence only when all of the following are true:

1. The normalized snapshot preserves explicit verified primary-provider contract lineage.
2. The physical capture event is readable from the local CSV cache.
3. The capture date is accepted by the declared offline market-session date policy.
4. The capture clock time maps to the predeclared acquisition frame.
5. The capture contributes either a new acquisition cell or an additional capture inside an already-covered cell.
6. The source remains clearly labeled as REAL and is not mixed with SAMPLE.

Historical availability, analytical eligibility and acquisition coverage answer different questions:

| Question | Layer |
| --- | --- |
| Can CSV snapshots be read and replayed? | Historical evidence |
| Is a row qualified for analytical workloads? | Analytical eligibility |
| Does a physical capture add predeclared time coverage? | Evidence accumulation |

Clock-session membership is not enough. A capture at `10:00` is only inside the configured morning clock window; it does not by itself prove that the capture calendar date is an eligible market-session date.

## Before Collection

Run local read-only checks first:

```bash
git status --short
python tools/probe_akshare.py --json
python tools/audit_provider_semantics.py --primary
python tools/audit_analytical_eligibility.py --source REAL --json
python tools/audit_evidence_accumulation.py --source REAL --json
```

Interpretation:

- `probe_akshare.py` may touch the provider for diagnosis, but it should not write `data/ticks`.
- `audit_provider_semantics.py` verifies the primary provider contract and runtime policy.
- `audit_analytical_eligibility.py` separates readable REAL history from qualified analytical readiness.
- `audit_evidence_accumulation.py` reports physical captures, market-session date states, qualified captures, covered cells and missing cells from existing local CSV only.
- `run_collection_session.py --json --no-network --no-log --max-runs 1` shows the current calendar date, market-session date state, active clock session and collection eligibility without writing CSV.

## Bounded Collection

Use one-shot or finite-run commands only:

```bash
python tools/collect_real_snapshot.py --dry-run
python tools/collect_real_snapshot.py
python tools/run_collection_session.py --max-runs 3 --interval-seconds 300 --respect-session --stop-on-contract-error
```

Rules:

- Start with `--dry-run` when validating provider availability and normalization.
- A normal REAL collection attempt must pass the market-session date gate before the clock-session gate. The default bundled policy is conservative: without declared offline calendar coverage, the date state is `market_calendar_unverified`.
- Do not use Streamlit page refreshes as a collection mechanism.
- Do not add `while True`, cron, launchd, Airflow, Celery, Redis or a custom background process inside the app.
- Do not replace the primary provider with another source unless semantic comparability has been designed and audited separately.
- Do not write SAMPLE or DEMO rows into `data/ticks`.

## After Collection

Run the evidence checks again:

```bash
python tools/inspect_history_evidence.py --source-mode REAL
python tools/audit_analytical_eligibility.py --source REAL --json
python tools/audit_evidence_accumulation.py --source REAL --json
python tools/smoke_check.py
python tools/verify_runtime.py
```

Confirm:

- New REAL cache files remain ignored by Git.
- Provider contract resolution for new captures is explicit verified.
- Qualified acquisition capture count increases only for eligible events.
- A capture with unresolved or ineligible market-session date state remains visible in the all-capture inventory but does not enter qualified acquisition coverage.
- Covered acquisition cell count increases only when a new predeclared cell receives its first qualified capture.
- Additional captures inside the same cell remain visible but do not inflate temporal coverage.
- Missing cells remain visible instead of being hidden behind aggregate snapshot counts.

## Go / No-Go For Qualified Multi-Day Evidence

Go when:

- Multiple trading dates contain explicit verified REAL captures.
- Qualified captures map into the acquisition frame.
- Coverage across sessions and dates is visible through covered and missing cell counts.
- Analytical eligibility reports qualified REAL observations for the relevant workload.

No-go when:

- REAL cache exists but provider contract lineage is unresolved.
- Captures are clustered in one or two cells and do not expand temporal coverage.
- Captures fall outside configured sessions.
- Captures occur on dates that are market-session ineligible or calendar-unverified under the declared offline policy.
- Only SAMPLE evidence is available.
- The app or tools would need network access or file writes during public demo checks.

## Safety Boundaries

- CSV remains the source of truth.
- SQLite remains a rebuildable local index.
- SAMPLE remains synthetic demo data.
- REAL cache stays local and ignored by Git.
- `trade_date` in normalized provider snapshots is the project observation-session date derived from `captured_at`; the current AKShare `今日` ranking path does not expose a provider-reported market reference date that the project preserves.
- Evidence labels describe observed historical coverage only.
- This protocol does not provide trading actions, fund selection, account integration or future-market conclusions.
