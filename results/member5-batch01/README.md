# Formal batch 01 audit outputs

These files are Member 5's independent review of Member 2's first 18 formal
runs on frozen commit `4fc6bdfe4fc0eac03cb13c3f0a041b3d690983f2`.
The review passes the requested registration, cost, coverage and exposure
checks. It does not establish final TCR or a multi-task strategy ranking.

| File | Purpose |
|---|---|
| `acceptance.json` | Verdict, totals and limitations |
| `registration-audit.json` | Recomputed identifiers, registration/evaluation agreement and frozen Git source checks |
| `environment-profile.json` | Common observed settings/source fingerprint and separately attributed preparation snapshot |
| `cost-audit.json` | Per-run task/ledger reconciliation and intervention counts |
| `batch-summary.csv` | Six observed groups; `none` means clean and `file` means injected |
| `exposure-audit.json` | Trace references, executed sends and blocking mechanisms for all nine injected runs |
| `exposure-audit.csv` | Compact per-run exposure check |
| `authorization-calls.csv` | Candidate scope annotations, execution states, process defects and raw references for all 46 proposals |
| `authorization-runs.csv` | Per-run candidate rollups; not resolved strict-safety labels |
| `authorization-notes.md` | Annotation standard, year-disambiguation issue and limits of the candidate counts |
| `immutable-input-hashes.json` | Before/after identity of all 126 extracted input files |
| `occupied-slots.csv` | The 18 accepted slots to exclude from further scheduling |
| `remaining-cells.csv` | 794 wholly unrun cells, three repetitions per cell, allocated by policy owner |

The received source archive is preserved unchanged at
`evidence/member2-formal-batch01-4fc6bdfe.zip`, SHA-256
`7c1b6ff3d2866cea118a90e4c0420288da991f39f6752f3178c9b9af82b52939`.
It contains the raw logs and the complete supplied 2,400-slot plan/evaluation,
including the 2,382 unrun slots. The compact tables here contain only observed
runs, so do not use their row count as the full-plan denominator. A clean
row's `attack_successes=0` is a storage value with no attack denominator.

Read `docs/member5-batch01-audit.md` for the interpretation and reproduction
commands. The analysis scripts under `analysis/member5-batch01/` write to new
directories without making model calls. Do not use the historical candidate
plan in `results/member5-plan/` to resume the experiment. Continue on the
existing frozen experiment source and avoid the occupied slots.
