# Member 5 validation record

Validation date: 28 October 2026, Asia/Shanghai. Inspected integration base:
`41a512b9aa1453c96b902915654489785c8e7d16`.

## First formal batch review on 30 October 2026

Member 2's 18-run archive at frozen experiment commit
`4fc6bdfe4fc0eac03cb13c3f0a041b3d690983f2` passes the independent registration,
accounting, coverage and trace-supported exposure checks. Registration and
evaluation were rerun under Python 3.11.18 and match the supplied outputs:
18 of 2,400 slots, 0 duplicates and 0 warnings. All 18 configuration IDs and
the recorded project/runner hashes were checked against frozen Git blobs.

The separate reconciliation finds 145,627 agent tokens, 22,324 Reviewer tokens,
15 actual reviews and complete recorded usage for 79 API attempts. There are
no retries or late rows in this batch. Exposure matches the supplied 8/9
classification; the unexposed run remains in the evidence. Read
`docs/member5-batch01-audit.md` for case analysis, runtime provenance and
continuation limits. This was an offline saved-data audit with zero new model
API calls, not another paid experiment or a new full-suite test run. The
experiment freeze and cost rules are unchanged. The separate annotation
script also reconciles all 46 proposals with the trajectory and records 16
year-disambiguation defects. Candidate scope labels remain outside the
strict-TCR registry; all 126 input files are unchanged.

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
