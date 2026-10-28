# Member 5 validation record

Validation date: 28 October 2026, Asia/Shanghai. Inspected integration base:
`41a512b9aa1453c96b902915654489785c8e7d16`.

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
