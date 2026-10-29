"""Evaluate saved logs offline; no AgentDojo install, credentials or paid calls."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evaluation import EvaluationError, evaluate, write_outputs


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", type=Path, help="Log directories; recursively discovers runs.")
    parser.add_argument("--registry", type=Path, help="JSON object mapping run_id to evidence metadata.")
    parser.add_argument("--plan", type=Path, help="JSON list of expected task runs, including missing/error runs.")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        registry = json.loads(args.registry.read_text(encoding="utf-8-sig")) if args.registry else None
        plan = json.loads(args.plan.read_text(encoding="utf-8-sig")) if args.plan else None
        if registry is not None and not isinstance(registry, dict):
            raise EvaluationError("Registry must be an object keyed by run_id")
        if plan is not None and not isinstance(plan, list):
            raise EvaluationError("Plan must be a list of expected task-run objects")
        report = evaluate(args.inputs, registry=registry, plan=plan)
        write_outputs(report, args.output)
    except (EvaluationError, OSError, ValueError) as e:
        parser.exit(2, f"Evaluation failed: {e}\n")
    print(f"Evaluated {len(report['tasks'])} task runs in {len(report['groups'])} groups; {len(report['warnings'])} warnings.")
    print(args.output / "evaluation.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
