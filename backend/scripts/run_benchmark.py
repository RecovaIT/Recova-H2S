"""
Recova benchmark CLI — Task 3.8 + 4.1.

Runs the 15-case BENCHMARK_SUITE through the real 6-agent pipeline and writes
benchmarks/results.json at repo root for the frontend dashboard to consume.

Usage (from backend/, .venv activated, DB running):
    python -m scripts.run_benchmark
    python -m scripts.run_benchmark --tracks core loop
    python -m scripts.run_benchmark --org-id <uuid>

Exit codes:
    0 — all cases passed
    1 — configuration error (no DB / no org / etc.)
    2 — one or more cases failed
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from app.benchmarks.runner import create_benchmark_run, execute_benchmark_run
from app.core.db import SessionLocal
from app.models.identity import Organization
from app.models.ops import BenchmarkCaseResult, BenchmarkRun

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_PATH = REPO_ROOT / "benchmarks" / "results.json"


def _serialize(br: BenchmarkRun, cases: list[BenchmarkCaseResult]) -> dict:
    return {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "suiteName": br.suite_name,
        "suiteVersion": br.suite_version,
        "algorithmVersion": br.algorithm_version,
        "tracks": br.tracks,
        "status": br.status,
        "totalCases": br.total_cases,
        "passedCases": br.passed_cases,
        "metrics": br.metrics,
        "cases": [
            {
                "caseId": c.case_id,
                "track": c.track,
                "scenario": c.scenario,
                "category": c.category,
                "expected": c.expected,
                "actual": c.actual,
                "passed": c.passed,
                "failureDetails": c.failure_details,
                "durationMs": c.duration_ms,
            }
            for c in cases
        ],
    }


def _print_summary(payload: dict) -> None:
    m = payload["metrics"]
    tp = m.get("true_positives", 0)
    fn = m.get("false_negatives", 0)
    tn = m.get("true_negatives", 0)
    fp = m.get("false_positives", 0)

    print()
    print("=" * 68)
    print(f"  Suite:     {payload['suiteName']}")
    print(f"  Version:   {payload['suiteVersion']} / algo {payload['algorithmVersion']}")
    print(f"  Cases:     {payload['passedCases']}/{payload['totalCases']} passed")
    print(f"  Tracks:    {', '.join(payload['tracks'])}")
    print("=" * 68)
    print(f"  Sensitivity:        {m.get('sensitivity_pct')}%  ({tp}/{tp + fn})")
    print(f"  Specificity:        {m.get('specificity_pct')}%  ({tn}/{tn + fp})")
    print(f"  Emergency accuracy: {m.get('emergency_detection_accuracy_pct')}%")
    print(f"  Missing-data pass:  {m.get('missing_data_pass_rate_pct')}%")
    print(f"  Consistency:        {m.get('scoring_consistency_pct')}%")
    print(f"  Agent failures:     {m.get('agent_execution_failures', 0)}")
    print(f"  Mean duration:      {m.get('mean_duration_ms')} ms")
    print(f"  Max duration:       {m.get('max_duration_ms')} ms")
    print("=" * 68)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Recova benchmark suite")
    parser.add_argument(
        "--tracks",
        nargs="+",
        default=["core", "loop", "neuro", "worksafe"],
        choices=["core", "loop", "neuro", "worksafe"],
    )
    parser.add_argument("--org-id", help="Organization UUID (defaults to first active org)")
    args = parser.parse_args()

    print(f"\nRecova benchmark — {len(args.tracks)} track(s): {', '.join(args.tracks)}")

    # Resolve target organization
    try:
        db = SessionLocal()
    except Exception as exc:
        print(f"\nERROR: could not open DB session: {exc}", file=sys.stderr)
        print("Check backend/.env — DATABASE_URL must point to a running PostgreSQL.", file=sys.stderr)
        return 1

    try:
        if args.org_id:
            org_id = uuid.UUID(args.org_id)
        else:
            org = db.scalar(select(Organization).where(Organization.is_active.is_(True)).limit(1))
            if org is None:
                print("\nERROR: no active organization found.", file=sys.stderr)
                print("Bootstrap the platform first: POST /api/v1/auth/bootstrap", file=sys.stderr)
                return 1
            org_id = org.id

        print(f"  Org:   {org_id}")
        print(f"  Out:   {OUT_PATH}")
        print()

        # Create + execute
        br = create_benchmark_run(db, organization_id=org_id, tracks=args.tracks)
        db.commit()

        print(f"  Running {len(args.tracks)} tracks … (this may take 1–3 minutes)")
        br = execute_benchmark_run(db, br.id)
        db.commit()

        # Fetch per-case results
        cases = list(
            db.scalars(
                select(BenchmarkCaseResult)
                .where(BenchmarkCaseResult.benchmark_run_id == br.id)
                .order_by(BenchmarkCaseResult.case_id)
            )
        )

        payload = _serialize(br, cases)

        # Write results
        OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUT_PATH.write_text(
            json.dumps(payload, indent=2, default=str),
            encoding="utf-8",
        )

        _print_summary(payload)
        print(f"\n  Wrote: {OUT_PATH}")

        # Report failures
        failed = [c for c in cases if not c.passed]
        if failed:
            print(f"\nFAILED CASES ({len(failed)}):", file=sys.stderr)
            for c in failed:
                print(f"  ✗ {c.case_id}: {c.failure_details}", file=sys.stderr)
            print()
            return 2

        print(f"\n  ✓ All {len(cases)} cases passed.\n")
        return 0

    except Exception as exc:
        db.rollback()
        print(f"\nERROR: benchmark execution failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())