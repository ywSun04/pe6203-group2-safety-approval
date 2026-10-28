# Candidate experiment plan

coverage.json and runner-commands.* describe the current proposal. No runs have
been executed. The source integration SHA is the inspected base commit; freeze
the final merged experiment commit before live execution.

Generate the detailed 2,400-slot evaluation plan and registry into a new folder:

```text
python scripts/member5_experiment_plan.py --output results/frozen-plan
```

The generator refuses to overwrite an existing folder. After receiving logs,
regenerate into another new folder using --logs and the agreed evidence kind.
Detailed generated rows are kept out of this PR to avoid repeating the same
metadata thousands of times; the local delivery package also includes a copy.
