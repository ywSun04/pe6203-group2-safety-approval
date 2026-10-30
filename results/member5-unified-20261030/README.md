# Unified M2/M6 evidence ledger

The current supplied evidence has 433 distinct run IDs. Under the reviewed
first-launch and scheduler mapping, there are 424 candidate primary positions,
two additional retries, three supplemental overlaps and four separate smoke
records. Running-owner acknowledgement remains pending for the scheduler
mappings. Raw manifests and original file bytes are unchanged.

| File | Contents |
|---|---|
| `summary.json` | Counts, attempt-role expenditure, unknown usage and limits |
| `run-ledger.csv` | All 433 UUIDs, original/derived repetition, role, primary link, costs and completeness |
| `m6-mapping-review.json` | Full M6 mapping with original hashes, scheduler evidence, backups and pending acknowledgement |
| `missing-slots.csv` | 1,976 reference positions not accounted for by supplied primaries, with owners and explicit execution=false |
| `group-metrics.csv` | Forty policy/k/condition groups, full denominators, strict unknowns and proxy bounds |
| `line-ending-evidence.json` | Known frozen LF/CRLF module/runner pairs and provenance limits |
| `older-handoff-check.json` | Byte identity of the older 405 records and the four added smoke UUIDs |
| `independent-check.json` | Separate raw-source recomputation of all role counts and costs |
| `source-provenance.json` | Original archive hashes and the curated evidence hash |

The four held BudgetAware top-up positions at task 0/k=1 and k=2 are included
in the uncovered list. The earlier 106-record CSV names two additional k=2
records that have not been supplied. A missing row here is not proof that no
later experiment exists and does not authorise payment.

The preserved evidence archive is `evidence/member5-unified-20261030.zip`.
It contains only unchanged run files, scheduler states and a source catalog,
not the M6 project source tree or personal drafts. The original M2 archives
are also preserved to reproduce the separate package-level batch-02 audit.

Run the command in `docs/member5-unified-reconciliation.md` to regenerate the
registry, detailed plan and evaluator output into a new local directory.
Generated working copies/full output are not checked in again. No credentials,
AgentDojo installation or model call is required for the unified data command.
The separate batch-02 exposure checker uses the pinned environment's PyYAML.

Formal execution remains on `4fc6bdfe4fc0eac03cb13c3f0a041b3d690983f2`.
Strict TCR is unresolved; completed utility and attacker-goal flags are narrower
observations. Candidate v3 studies and smoke observations remain separate.
