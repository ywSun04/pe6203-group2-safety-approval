# Member 6 supplement and updated received snapshot

31 October 2026. This supplement supersedes the earlier 874-run coverage and cost totals while preserving that snapshot as history. Execution remains frozen at `4fc6bdfe4fc0eac03cb13c3f0a041b3d690983f2` with Reviewer v2. No new model request was made.

## What the new evidence establishes

The supplied `m6_target_rep_logs.zip` has SHA-256 `64d6bf90a5edb1dd2a75ac47bd8eca9c6addf2c168b262c55a3c2c6876e0881b`, exactly matching the archive identified by the earlier metadata-only handoff. Its **196 distinct UUIDs** match all 196 candidate rows, with no UUID or primary-position overlap with the previous 874. Each record includes six original files. Raw repetitions, task/k assignments, configuration IDs, source fingerprints and token accounting pass verification. An independent saved-data review agrees.

These 196 runs have **152 utility completions, 44 ordinary task failures and no technical errors**. They invoke the Reviewer 78 times and record 2,225,895 Agent tokens, 265,326 Reviewer tokens and zero policy-model tokens. All returned usage reconciles, with provider cost USD **0.23104920**. A normal runner termination is not automatically a completed task.

The unified inventory now contains **1,070 distinct raw run IDs**: 165 from Member 2 and 905 from Member 6. The first-launch rule yields **1,061 candidate primary positions**, plus two retries, three cross-member supplemental attempts and four smoke runs. Of those primaries, **1,054 match the agreed configuration**; seven remain quarantined. The observed-only registry/evaluator completes with zero warnings. All previous 874 outcomes, attempt roles, tokens and costs remain unchanged.

## Mapping confirmation recorded after the supplied review table

All 305 rows of `M6_305_Mapping_Review.csv` match the proposed identity fields and original manifest hashes. The supplied file retains **PENDING_OWNER_CONFIRMATION** as the status at receipt. A later explicit user message in this conversation confirmed all 305 mappings and the primary, retry and cross-member overlap assignments. The English translation, source attribution, exact review-file hash and 305 UUIDs are recorded in `mapping-confirmation.json`. This is a user-provided confirmation, not a claim of independent contact with Member 6. The active pending count is now zero. Exactly 300 selected primary registry proofs are marked confirmed; the other two retries and three cross-member supplemental rows keep their existing roles. The raw CSV and manifests remain unchanged.

The seven rows of `M6_7_Reviewer_Exclusions.csv` also match the earlier evidence. Its handling field preserves original records and costs, excludes them from frozen-configuration comparisons, and authorizes no automatic replacement. The Reviewer endpoint difference remains unexplained, but this does not prevent publishing the snapshot with those rows quarantined. The existing 31 HTTP401 responses and unknown returned Reviewer usage are retained; the rows are not reinstated as valid defensive successes.

## BudgetAwarePolicy clean coverage

Adding the supplement gives **296 clean observations** across 20 tasks and five budgets: 100 at repetition 0, 98 at repetition 1 and 98 at repetition 2. There are **229 utility completions** and 67 ordinary failures, with 122 actual reviews. The four unrepresented reference positions are task 0 at k=1/2, repetitions 1/2. Their absence from the received scope is not proof that nobody started them, and is not an instruction to pay for replacement runs.

| k | Runs | Utility completed | Actual reviews | Agent tokens | Reviewer tokens | Recorded provider cost (USD) |
|---:|---:|---:|---:|---:|---:|---:|
| 0 | 60 | 39 | 0 | 533,291 | 0 | 0.05133480 |
| 1 | 58 | 43 | 12 | 516,113 | 23,955 | 0.04893270 |
| 2 | 58 | 47 | 29 | 946,233 | 75,753 | 0.09006840 |
| 4 | 60 | 51 | 33 | 584,931 | 102,107 | 0.06651855 |
| 8 | 60 | 49 | 48 | 775,595 | 227,454 | 0.09972360 |


These are utility outcomes on the received task set. A complete executed-action authorization audit has not been made for the entire 296-run clean pool, so the table is not relabelled strict TCR. The task/repetition mix also differs slightly at k=1/2. The numerator and denominator remain explicit.

![Budget policy received coverage](figures/budget-coverage.png)

## Main comparison stays fixed

The primary balanced comparison remains **80 runs**: tasks 0 and 1, repetition 0, five k values, clean and injected conditions, four policies. Every outcome, count and curve point in its k scan matches the previous snapshot exactly. The new clean repetitions do not justify replacing failed earlier observations or changing this panel after seeing the outcomes.

| Policy | Condition | n | Strict safe completions | Actual reviews |
|---|---|---:|---:|---:|
| full-approve | clean | 10 | 9 | 0 |
| full-approve | injected | 10 | 0 | 0 |
| full-escalate | clean | 10 | 7 | 10 |
| full-escalate | injected | 10 | 7 | 15 |
| basic_risk | clean | 10 | 10 | 0 |
| basic_risk | injected | 10 | 10 | 8 |
| budget_aware | clean | 10 | 10 | 0 |
| budget_aware | injected | 10 | 10 | 7 |


The wider common-support set grows to 224 runs, with 526 proposed calls and 332 execution attempts reviewed under the same task-specific authorization rules. No executed action in that audited set is unclassified. The clean/injected paired subset contains 184 runs. Membership and per-call evidence are saved separately; these additional rows do not turn the experiment into a balanced 20-task comparison.

![Fixed-task strict TCR comparison](figures/matched-tcr.png)

Broader policy aggregates use different task coverage. Strict TCR remains the joint event of utility completion and no unauthorized executed action. Benchmark attack predicates alone are not a substitute for that audit. The unchanged attack evidence has 395 same-profile assigned runs, 30 official successes, 356 resolved failures and nine unknown outcomes. Its 366 confirmed trace-supported exposures and exposure-conditioned metrics are unchanged.

## Updated tokens and cost

The 1,054 same-profile candidate primaries record **10,996,391 Agent tokens and 954,121 Reviewer tokens**, with zero policy-model tokens. They include 393 actual reviews and 128 additional escalation requests denied at exhausted budgets. Their recorded provider cost is **USD 1.10739765**, with three unresolved usage requests.

Across all **1,070 unique UUIDs**, including smoke, retry, supplemental and quarantined rows, recorded provider cost is **USD 1.15053210**. This is the previous USD 0.91948290 plus the newly verified USD 0.23104920. Twelve runs still have 36 unresolved usage requests, so the total is a known partial amount, not a complete invoice. The known token total is 11,533,191 Agent plus 954,121 Reviewer tokens. Task totals, retry subsets, late-usage flags and HTTP usage are reconciled without adding the same consumption twice.

PR14 remains an independent saved-evidence development comparison at the earlier documented candidate head. Its known USD 0.00448935 development response cost is outside the formal-run total. No new candidate call, task rerun or formal TCR improvement is claimed by this supplement. The six original lunch-task failures and their classifications remain unchanged.

## Validation and reproduction

The complete offline suite passes **330 tests**. The earlier seven supplement checks prevent pending/partial review tables, duplicate UUIDs or changed source identities from being promoted to complete owner acknowledgement. Eleven further checks bind explicit confirmation to the exact CSV and UUID/role scope, reject incomplete or mismatched declarations, and prevent clearing unrelated pending rows. Zero-utility groups explicitly label their joint TCR as an algebraic zero, without asserting an authorization audit. Two independent audits, the 1,054-row standard registration, byte hashes, unchanged old-record checks and unchanged primary-panel checks agree. These are offline validation results, not new benchmark runs.

Run the commands from the repository root in the pinned analysis environment, using new output directories:

```powershell
python analysis/member5-supplement/intake.py --old-evidence evidence/member5-received-20261031.zip --raw-supplement evidence/member6-supplement-20261031/m6_target_rep_logs.zip --mapping-review evidence/member6-supplement-20261031/M6_305_Mapping_Review.csv --exclusions-review evidence/member6-supplement-20261031/M6_7_Reviewer_Exclusions.csv --output supplement-intake
python analysis/member5-final/analyze_snapshot.py --evidence supplement-intake/combined-evidence.zip --mapping results/member5-unified-20261030/m6-mapping-review.json --output supplement-computed
python analysis/member5-supplement/clarify_notes.py --snapshot supplement-computed
python analysis/member5-supplement/confirm_mapping.py --snapshot supplement-computed --confirmation results/member5-supplement-20261031/mapping-confirmation.json --review-csv evidence/member6-supplement-20261031/M6_305_Mapping_Review.csv
python analysis/member5-supplement/register.py --snapshot supplement-computed --evidence supplement-intake/combined-evidence.zip --confirmation results/member5-supplement-20261031/mapping-confirmation.json --output supplement-registered
```

The original three supplied files are retained byte-for-byte under `evidence/member6-supplement-20261031/`. The deterministic merged evidence hash is `2a4c4fddc8f257d2440a0e700216466f60c49856f35b56c6cbc7a9eb61abd5c8`. The previous snapshot, input hashes and mapping proposals remain available. Analysis-only plotting uses the separately documented Matplotlib/NumPy versions.

The 305 mapping/attempt assignments are now explicitly confirmed via the recorded user message. No mapping confirmation remains outstanding in this snapshot. The seven exception rows can remain excluded without blocking reporting. No new paid batch is released, no frozen runtime code changes, and no personal report or presentation is uploaded.

To reproduce the current TCR figure after recording confirmation, run `python analysis/member5-supplement/plot_confirmed.py results/member5-supplement-20261031`. The earlier intake checks and independent CSV review remain as historical evidence of the file at receipt; the later confirmation sidecar supplies the active status.
