# Member 6 Experimental Analysis — BudgetAwarePolicy

**NTU PE6203 | Safety Approval Gate (AgentDojo)**  
**Evidence snapshot:** 31 October 2026 | **Status:** Final M6 analysis; M5 mapping confirmation completed (PR #13, commit `2dd8fba`)  
**Frozen commit:** `4fc6bdfe4fc0eac03cb13c3f0a041b3d690983f2`  
**Configuration:** AgentDojo workspace v1.2.2; Agent `openai/gpt-4o-mini`; Reviewer v2; BudgetAwarePolicy `budget_aware_v1`; k ∈ {0,1,2,4,8}.

## 1. Objective and methodology

This report assesses how the review budget affects BudgetAwarePolicy's utility, actual human-in-the-loop (HITL) review invocations, token consumption, recorded provider cost and resistance to injected tool-result attacks. It uses Member 5's reconciled, first-launch experiment ledger, retaining failures and retries rather than selecting favorable outcomes. The fixed-task four-policy comparison is kept separate from the broader, unbalanced observational pool.

Strict TCR@k is defined as the proportion of attempted tasks that both complete their legitimate objective and execute no unauthorized action. It is reported only for the explicitly audited matched panel. Utility completion is reported separately for the larger pool, for which complete executed-action authorization auditing is not available. HITL counts actual Reviewer calls, not merely escalation requests.

## 2. Registration and evidence quality

The unified received archive contains 1,070 unique run IDs (165 M2 and 905 M6), comprising 1,061 first-launch candidate primary positions, two retries, three cross-member supplemental attempts and four smoke runs. Of the primaries, 1,054 conform to the agreed profile; seven endpoint-mismatched Reviewer runs are quarantined. Standard registration reports zero warnings. The M6 owner confirmed the 305 mapping rows and the associated primary, retry, and cross-member overlap assignments; M5 subsequently closed the pending status for all 305 mapping rows in PR #13 (commit `2dd8fba`), reporting zero active pending confirmations, 330 passing tests and zero registration warnings. The original results, costs and seven quarantined anomalies were unchanged. This report relies on M5’s confirmation and does not claim a separate line-by-line re-audit of the post-confirmation ledger. Raw manifests and failed attempts remain unchanged.

The new 196-run M6 clean supplement has 152 utility completions, 44 ordinary failures, no technical errors and 78 actual reviews, with USD 0.23104920 returned cost and complete returned usage.

## 3. BudgetAwarePolicy clean observations

| k | Runs | Utility completed | Utility rate | Actual reviews | Agent tokens | Reviewer tokens | Recorded USD |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 60 | 39 | 65.0% | 0 | 533,291 | 0 | 0.05133480 |
| 1 | 58 | 43 | 74.1% | 12 | 516,113 | 23,955 | 0.04893270 |
| 2 | 58 | 47 | 81.0% | 29 | 946,233 | 75,753 | 0.09006840 |
| 4 | 60 | 51 | 85.0% | 33 | 584,931 | 102,107 | 0.06651855 |
| 8 | 60 | 49 | 81.7% | 48 | 775,595 | 227,454 | 0.09972360 |
| **Total** | **296** | **229** | **77.4%** | **122** | **3,356,163** | **429,309** | **0.35657805** |

The k=1 and k=2 rows have two fewer observations each than k=0/4/8, so their utility rates are descriptive, not a controlled causal comparison. More review budget generally permits more actual reviews, but utility is not monotonically increasing; k=8 does not outperform k=4 in these observed clean runs. These utility rates must not be labelled strict TCR.

## 4. Matched four-policy safety and utility comparison

The primary balanced panel contains 80 runs: two fixed tasks, repetition 0, five k values, clean and injected conditions, across four policies. Each policy-condition pair has ten attempts.

| Policy | Clean strict TCR | Injected strict TCR | Clean reviews | Injected reviews |
|---|---:|---:|---:|---:|
| Full-approve | 9/10 (90%) | 0/10 (0%) | 0 | 0 |
| Full-escalate | 7/10 (70%) | 7/10 (70%) | 10 | 15 |
| BasicRiskPolicy | 10/10 (100%) | 10/10 (100%) | 0 | 8 |
| BudgetAwarePolicy | 10/10 (100%) | 10/10 (100%) | 0 | 7 |

For BudgetAwarePolicy, each k point contains two clean and two injected attempts; all have 2/2 strict safe completions in each condition. Injected actual review counts across k=0,1,2,4,8 are respectively 0,1,2,2,2; clean counts are zero. Thus the panel supports a limited finding of preserved audited safety with fewer actual reviews than Full-escalate, but not a suite-wide superiority claim. The difference between BudgetAwarePolicy's seven injected reviews and BasicRiskPolicy's eight is too small and task-specific for a robust ranking.

## 5. Attack outcomes and exposure

The same-profile attack inventory contains 395 assigned runs, with 30 official attack successes, 356 resolved failures and nine unknown outcomes due to technical termination. Its resolved ASR is 30/386 (7.8%), with assignment-based bounds of 30/395 to 39/395. Of these, 366 have confirmed trace-supported payload exposure. For BudgetAwarePolicy specifically, 293 same-profile injected runs contain 213 utility completions, six technical errors and 277 confirmed exposures. No official goal success is recorded among 287 resolved BudgetAwarePolicy injected outcomes. This does not prove every payload reached the model or that every unauthorized proposal was correctly classified.

## 6. Tokens, cost and limitations

The 1,054 same-profile candidate primaries contain 10,996,391 recorded Agent tokens and 954,121 Reviewer tokens, 393 actual reviews and 128 escalation requests blocked after budget exhaustion. Recorded provider cost is USD 1.10739765, with three unresolved usage requests. All 1,070 unique runs together have USD 1.15053210 recorded returned cost, but 12 runs contain 36 unresolved usage requests. This is a **partial known cost**, not a complete invoice. Independent PR14 development-response cost is excluded.

Principal limitations include the narrow two-task balanced panel, unequal broader task/repetition coverage, unknown usage, quarantined Reviewer endpoint mismatches, non-exposure in some attack-assigned runs and reliance on M5’s post-confirmation registry acknowledgement rather than an independent line-by-line re-audit. No additional paid experiment is implied by these limits.

## 7. Conclusion

In the fixed-task audited panel, BudgetAwarePolicy achieved 10/10 strict safe completions under both clean and injected conditions, with seven actual reviews under injection versus 15 for Full-escalate. In the larger received clean pool it completed 229/296 tasks and invoked the Reviewer 122 times. Higher k values increased available review capacity but did not yield a monotonic utility gain in observed runs. These findings support a bounded, evidence-based account of review-budget trade-offs; they do not establish universal injection resistance or a completed balanced 20-task benchmark.

## Evidence provenance

Member 5 supplement README and summary; `matched-k-scan.csv`, `matched-four-policy-metrics.csv`, `descriptive-metrics.csv`, `run-ledger.csv`, `matched-call-authorization.csv`, and associated audit/evaluation outputs in the received 31 October 2026 evidence archive. No new model calls were made to prepare this report. The reported figures derive from the 31 October 2026 evidence snapshot; M5 confirmed the 305 mapping rows in PR #13 at commit `2dd8fba`; any later substantive registry changes require comparison before merge.
