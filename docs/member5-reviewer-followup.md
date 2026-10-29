# Member 5 check of Reviewer development evidence

On 29 October 2026, I checked Member 4's three saved development reports against
their API usage ledgers in `docs/evidence/reviewer-phase2/`. The case counts,
manual-label matches, technical failures, unknown usage and observed token sums
agree. The recomputed rows are in
`results/member5-reviewer-development-summary.csv`.

| Check | Manual-label matches | Model decision mismatches | Technical failures | Observed tokens | Cases with unknown usage |
|---|---:|---:|---:|---:|---:|
| v1, 30s review / 2s connect | 14/17 | 2 | 1 | 12,026 | 1 |
| v2, 30s review / 2s connect | 15/17 | 1 | 1 | 14,452 | 1 |
| v2 diagnostic, 30s review / 10s connect | 2/2 | 0 | 0 | 1,947 | 0 |

A timeout is a technical failure, even when the final fail-closed result is
DENY. It is not counted as a correct Reviewer judgment. Each full pass has
17 recorded attempts and 16 responses; its unresolved attempt remains unknown
usage. The diagnostic has two attempts and two responses. The known response
tokens match each report's observed subtotal. Unknown requests may still have
incurred cost, so these subtotals are not complete billed totals.

The calendar query's false denial was reproduced with v1 and approved with v2.
Both full passes still rejected the current-day discovery query. Its later
approval belongs to a separate diagnostic with a different connection cap;
it does not overwrite the earlier failure or establish a stable fix.

These are development cases with manual expectations, not held-out accuracy,
AgentDojo task-completion results or TCR@k. Keep each prompt and timeout setting
separate. The table also excludes the six original Gate smoke runs and Member
4's preliminary connection probes; it should not be presented as total project
or account expenditure. No new API request was made for this check.
