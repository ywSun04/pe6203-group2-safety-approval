# Member 5 validation record

## Received snapshot checks, 31 October

The full offline suite passes **312 tests** in Python 3.11, including six new
exposure checks for wrapped YAML, incomplete payloads, failed tool results,
user-message marker spoofing and missing/changed-history continuations.
The saved-data workflow verifies all 874 UUIDs and original companion hashes,
reconciles per-run token accounting without discrepancies, reproduces M2's
165 registrations and zero evaluator warnings, and matches its supplied group
metrics. It checks 300 M6 attack launch claims and all 464 proposed calls in
the broad matched intersection. There are no unknown executed-action labels
in that audited panel. Raw files are byte-preserved.

The PR14 comparison verifies the five actual false-denial proposals against
the saved replay task, arguments, available budget and pre-proposal history.
The pending assistant tool-call message and metadata differ in the replay,
which is disclosed. The hypothetical Gate-blocked sixth lunch is excluded.
No new API request or formal experiment was run.

The two PNG/PDF research figures were rendered and visually checked. Plotting
used Matplotlib 3.11.2 and NumPy 2.4.6 in the isolated analysis environment;
these optional plotting dependencies do not alter frozen runtime requirements.
See [the dated results and limitations](../results/member5-final-20261031/).
The sections below retain historical validation records.

Validation date: 28 October 2026, Asia/Shanghai. Inspected integration base:
`41a512b9aa1453c96b902915654489785c8e7d16`.

## Unified evidence review, 30 October 2026

The analysis-only reconciliation additions pass the full project suite:
**306 tests in 14.52 seconds**, Python 3.11.18. This includes fingerprint-drift
rejection, exact manifest binding, explicit repetition types/evidence,
failure-first selection, archive path/hash guards, unknown usage and late/retry
accounting. No frozen Gate, policy, Reviewer, runner, dependencies or fixtures
were changed.

An end-to-end saved-data run verifies 433 unique raw UUIDs and produces 424
candidate primary positions, two extra retries, three supplemental overlaps
and four separate smoke observations. Accounting has zero discrepancies and
the evaluator has zero warnings. An independent second calculation matches
the raw token/review/cost totals and checks every curated companion byte against
its original archive. Owner acknowledgement remains explicit and pending.

The original M2 batches alone also reproduce the supplied registration and
evaluation exactly: 24 positions, zero warnings. The six new task-6 observations
retain five false Reviewer denials, one correct malicious-deletion denial and
the separate Gate budget block, consistent with the received M4 assessment.
The opt-in reconciliation does not relabel those model decisions or strict
safety outcomes. Full details are in `docs/member5-unified-reconciliation.md`.

All of these are offline checks with zero new model API calls. Historical test
counts below describe their original validation dates, not additional experiments.

## LF and hash repair on 29 October 2026

The freeze at `ccf3051c96505f655de169e7613ab6722fec6a4c` was reproduced in a
clean LF copy: **263 passed, 2 failed**. All 20 fixture hashes matched a CRLF
conversion, not the LF Git blobs. This explains why the earlier Windows
validation passed but did not transfer to an LF checkout.

Member 2's patch pins fixture/configuration JSON to LF and updates the 20
manifest hashes. All 22 fixture blobs, including retired files, are unchanged.
The repaired suite passes **267 tests in 13.61 seconds** under Python 3.11.18:
the original 265 plus two checkout regression cases. The cases exercise Git
checkout conversion under both autocrlf settings. Offline validation again
passes all 20 task/fixture pairs. No model API was called.

The candidate coverage, validation JSON and matrix now use the corrected
fingerprints. The old freeze is invalidated; a new main SHA and freshly
generated plan are required after this fix is merged. Full reproduction and
patch attribution are in `docs/member5-hash-fix.md`. The earlier records below
are retained as historical validation, not evidence of LF portability.

## Earlier Reviewer v2 follow-up on 29 October 2026

Main commit `babab1cea382c6de61ab42312439020dd6816a2b` (PR #7) has been
integrated into the Member 5 branch. The full suite passes **265 tests** under
Python 3.11.18: the 211-test shared baseline plus 54 Member 5 tests. The run
took 13.15 seconds, with one warning about an unwritable local pytest cache;
test temporary files were kept in the workspace. No model API was called.

The English handoff is now `docs/member5-handoff.md`; the Chinese submission
document and its README link have been removed. Personal report, slide and
speaking-note drafts remain excluded. The calendar-call annotation now cites
Member 4's assessment from PR #7. Original smoke logs, costs and whole-run
safety labels are preserved.

Reviewer v2 prompt SHA-256:
`f65dcec71074a8402c7a094e4f4976cc95a33b655e0d7084563ecbf602f040a9`.
The candidate plan has been refreshed against that prompt. It still makes no
API calls and is not the final experiment freeze. Member 1 must announce the
final main SHA after PR #6 is merged.

The refreshed preview contains 2,400 unrun slots. A registration check rejects
the historical v1 `member2-review-connect2` run against the v2 prompt, and all
2,400 missing slots remain represented in the evaluator. This checks the
registration path without making model calls; it is not a received live batch.

Member 4's three saved development reports also reconcile with their usage
ledgers. The separate table in `docs/member5-reviewer-followup.md` keeps model
decision errors, technical failures and unknown usage apart. These rows are not
formal results and are not added to the six historical smoke-run totals.

## Original checks on 28 October 2026

The pinned AgentDojo source is
`089ed468cf3ed0322acc66b0211f26d9d90dbf60`, workspace v1.2.2. The source checker
confirmed the commit in the Python 3.11 environment. A separate local-source
installation was also checked by comparing installed Python source bytes with
the pinned checkout before the fixture validation was accepted.

| Check | Result |
|---|---|
| Full project suite, Python 3.11.18 | 263 passed in 16.58 seconds |
| Full project suite, Python 3.12.14 | 263 passed in 12.46 seconds |
| New metric and plan tests | 46 passed |
| New fixture and serialization tests | 8 passed |
| Current fixture loader/reference delivery/reference utility/predicate self-check | 20 of 20 in each check |
| Six archived live smoke runs ingested | 6 task runs, 0 accounting warnings |
| Detailed proposed grid generated | 2,400 slots, 40 command groups, 0 matched executions |
| Saved source compiled and Git whitespace checked | Passed |

The 263 tests comprise the 209-test shared baseline plus 54 added tests.
pytest 9.1.1, OpenAI SDK 3.39.0 and HTTPX 0.28.1 were used. Tests use simulated
responses and AgentDojo's in-memory environment. No model API was called by this
Member 5 validation. The existing six live smoke runs were produced previously
by Member 2 and audited here; they were not rerun or relabelled formal.

The two rejected historical email-goal fixtures are retained only for a
regression check. Their replacements pass the original official predicate;
the predicate itself was not changed. Current hashes and provenance are in
`configs/member5/attack-manifest.json` and the validation JSON.

Personal report, slide and speaking-note drafts are retained locally and are
not part of this handoff. The evaluator SVG
preserves gaps for unresolved strict TCR and explicitly labels the absence of
formal evidence. Late tokens already included in task totals are not added
again. Provider cost observations are diagnostic fields, not a verified bill.

Reproduce after installing the group's pinned requirements:

```text
python scripts/check_agentdojo.py
python -m pytest tests -q
python scripts/validate_member5_attacks.py --output local-validation.json
python scripts/evaluate_logs.py EXTRACTED_LOG_ROOT --registry configs/member5-smoke-registry.json --output local-smoke
python scripts/member5_experiment_plan.py --output local-frozen-plan
```

The detailed checked-in coverage describes a candidate plan based on the
inspected integration base. Regenerate the plan on the final agreed experiment
commit before live execution, preserve failures and unattempted slots, and
register actual UUIDs against their planned conditions. These checks establish
implementation and offline compatibility, not live injection efficacy or
formal strategy performance.
