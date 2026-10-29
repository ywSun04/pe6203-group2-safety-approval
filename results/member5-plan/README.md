# Candidate experiment plan

coverage.json and runner-commands.* are a candidate preview refreshed on
29 October 2026 using Reviewer v2 from main commit
`babab1cea382c6de61ab42312439020dd6816a2b`. No runs have been executed.
This inspected base SHA is not the final freeze: PR #6 still needs to be merged.
Regenerate the plan on the final main commit announced by Member 1 before any
formal run. Do not register new v2 runs with the old v1 preview.

Generate the detailed 2,400-slot evaluation plan and registry into a new folder:

```text
python scripts/member5_experiment_plan.py --output results/frozen-plan
```

The generator refuses to overwrite an existing folder. After receiving logs,
regenerate into another new folder using --logs and the agreed evidence kind.
Detailed generated rows are kept out of this PR to avoid repeating the same
metadata thousands of times; the local delivery package also includes a copy.

The runner does not resume repetitions. Continue a small batch with disjoint
task/policy/k/condition cells; reusing a completed cell restarts repetition zero
and registration will reject the duplicate. See `docs/member5-handoff.md`.
