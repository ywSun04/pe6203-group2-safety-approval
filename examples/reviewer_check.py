"""Opt-in live development-case check; labels never enter Reviewer requests."""
import argparse
import json
import os
import uuid
from pathlib import Path

from reviewer.llm_reviewer import LlmReviewer, PROMPT_SHA256


def evaluate(reviewer, cases, timeout=30):
    rows = []
    for case in cases:
        error = None
        decision = None
        reason = None
        try:
            result = reviewer.review(case["request"], timeout_seconds=timeout)
            decision, reason = result["decision"], result["reason"]
        except Exception as exc:
            # Never record raw exception details from providers.
            error = type(exc).__name__
        rows.append(dict(id=case["id"], expected=case["expected_decision"],
                         decision=decision, error=error, reason=reason,
                         final_decision=decision or "DENY",
                         technical_failure=error is not None,
                         correct=error is None and decision == case["expected_decision"],
                         tokens_observed=reviewer.last_token_usage,
                         usage_known=reviewer.last_usage_known,
                         latency_seconds=reviewer.last_latency_seconds))
        print(f"{case['id']}: {decision or error}", flush=True)
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", choices=["v2", "v3"], default="v2")
    parser.add_argument("--live", action="store_true", help="Enable paid model requests")
    parser.add_argument("--cases", type=Path, nargs="+", default=[Path(__file__).resolve().parents[1]/"reviewer/cases/authorization.json"])
    parser.add_argument("--output", type=Path, default=Path("logs")/f"reviewer-{uuid.uuid4().hex}.json")
    parser.add_argument("--timeout", type=float, default=30)
    parser.add_argument("--connect-timeout", type=float, default=2)
    args = parser.parse_args()
    if not args.live:
        parser.error("Add --live after local REVIEWER_* configuration; this incurs API cost")
    import math
    if any(not math.isfinite(x) or x <= 0 for x in [args.timeout, args.connect_timeout]):
        parser.error("Timeouts must be finite and positive")
    required = ["REVIEWER_MODEL", "REVIEWER_API_KEY"]
    if any(not os.environ.get(k) for k in required):
        parser.error("Set REVIEWER_MODEL and REVIEWER_API_KEY locally")
    if args.output.exists() or args.output.with_suffix('.usage.jsonl').exists():
        parser.error("Choose a fresh output path to avoid mixing runs")
    cases = [case for path in args.cases for case in json.loads(path.read_text())]
    if len({c['id'] for c in cases}) != len(cases):
        parser.error("Case IDs must be unique")
    # Reuse Member 2's connection cap and missing-usage accounting.
    from experiments.run_suite import UsageLedger
    import httpx
    from openai import OpenAI
    run_id = uuid.uuid4().hex
    usage_path = args.output.with_suffix('.usage.jsonl')
    ledger = UsageLedger(usage_path, run_id, "reviewer", connect_timeout=args.connect_timeout)
    client = OpenAI(api_key=os.environ['REVIEWER_API_KEY'], max_retries=0,
                    base_url=os.environ.get('REVIEWER_BASE_URL', 'https://api.openai.com/v1'),
                    http_client=httpx.Client(event_hooks={"request":[ledger.request],"response":[ledger.response]}))
    reviewer_class = LlmReviewer
    if args.candidate == "v3":
        from reviewer.temporal_v3 import TemporalReviewerV3
        reviewer_class = TemporalReviewerV3
    reviewer = reviewer_class(os.environ['REVIEWER_MODEL'], client)
    try:
        rows = evaluate(reviewer, cases, args.timeout)
    finally:
        client.close()
    report = dict(evidence="development cases, not held-out benchmark", run_id=run_id,
                  model=reviewer.model, reviewer=reviewer.name, prompt_sha256=reviewer.prompt_sha256,
                  timeout_seconds=args.timeout, connect_timeout_seconds=args.connect_timeout,
                  correct=sum(r['correct'] for r in rows), total=len(rows), cases=rows,
                  technical_failures=sum(r['technical_failure'] for r in rows),
                  observed_tokens=sum(r['tokens_observed'] for r in rows),
                  unknown_usage_count=sum(not r['usage_known'] for r in rows),
                  cost_note="Observed usage only; missing usage requires provider reconciliation. Retry count is zero.")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(f"Development cases: {report['correct']}/{report['total']}; technical failures: {report['technical_failures']}; report: {args.output}")


if __name__ == '__main__':
    main()
