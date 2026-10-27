"""Live check of synthetic cases. Labels stay outside Reviewer requests.

Run only after local REVIEWER_* configuration. This incurs model API cost.
"""
import argparse
import json
from pathlib import Path
from approval_gate.reviewer import invoke_reviewer
from reviewer.llm_reviewer import LlmReviewer, PROMPT_SHA256


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Explicitly enable paid API calls")
    parser.add_argument("--output", type=Path, default=Path("logs/reviewer-check.json"))
    args = parser.parse_args()
    if not args.live:
        parser.error("Use --live after configuring REVIEWER_MODEL and REVIEWER_API_KEY; this calls the model")
    reviewer = LlmReviewer.from_env()
    cases = json.loads((Path(__file__).resolve().parents[1] / "reviewer/cases/authorization.json").read_text())
    rows = []
    for case in cases:
        result = invoke_reviewer(reviewer, case["request"])
        # Snapshot inside outer gate deadline can be incomplete on timeout.
        rows.append(dict(id=case["id"], expected=case["expected_decision"], decision=result.decision,
                         error=result.error, tokens_observed=result.token_usage,
                         reason=result.reason, correct=result.decision == case["expected_decision"]))
    report = dict(evidence="synthetic cases, not AgentDojo benchmark", model=reviewer.model,
                  reviewer=reviewer.name, prompt_sha256=PROMPT_SHA256,
                  correct=sum(row["correct"] for row in rows), total=len(rows), cases=rows,
                  cost_note="Observed tokens only. Missing/late provider usage may undercount cost; gate logs are authoritative for task runs.")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2)+"\n")
    print(f"Synthetic check: {report['correct']}/{report['total']}; output: {args.output}")


if __name__ == "__main__":
    main()
