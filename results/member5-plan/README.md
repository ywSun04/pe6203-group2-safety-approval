# Candidate experiment plan

coverage.json and runner-commands.* are a candidate preview refreshed for the
LF/hash repair on 29 October 2026. They use the corrected attack-pack hash and
the unchanged Reviewer v2 prompt. No runs have been executed.

The recorded integration SHA `ccf3051c96505f655de169e7613ab6722fec6a4c` is the
inspected pre-fix base. That freeze failed the LF checks and must not be used
for formal runs. The coverage status marks this preview as pending the fix and
refreeze. After the fix is merged, regenerate the plan on the new main SHA
announced by Member 1. See `docs/member5-hash-fix.md`.

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
