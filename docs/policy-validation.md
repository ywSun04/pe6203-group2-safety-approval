# Risk policy validation record

Validation date: 26 October 2026. The shared base is repository revision 5eb4f9237ef271ac03daacbfea18199b32fadb50. The AgentDojo source is 089ed468cf3ed0322acc66b0211f26d9d90dbf60, verified through installed PEP 610 direct_url.json. Its distribution still reports 0.1.35. The current policy name is basic_risk_v2, which separates this revision from earlier experiment caches.

The local environment is Windows with Python 3.11.9 and pytest 9.1.1 in a repository-local virtual environment. The policy uses the standard library and needs no model key. The original runtime VCS pin is unchanged. requirements-dev.txt adds pytest.

## Commands and actual results

`python scripts/check_agentdojo.py` confirmed the source commit. `python -m pip check` reported no broken requirements. These checks apply to the environment used here, not every future dependency resolution.

`python -m pytest -q` passed 117 cases. The policy-related suite contains 101 cases. The existing shared suite contains 16. The earlier policy revision passed 70 added cases and 86 in total; those historical counts should not be presented as the current count.

`python -m examples.risk_policy` produced six valid two-field outputs. These cover local approval, ordinary external-action review, direct credential denial, an exhausted escalation request, a user prohibition, and a wrong recipient under a supported explicit scope.

`python -m examples.gate_smoke --log-dir <local-directory>` completed with local fake tools and FakeReviewer. No mail or model call occurred. The five final decisions were APPROVE, APPROVE, DENY, DENY, APPROVE; after-call budgets were 1, 0, 0, 0, 0. There were two requested reviews and one actual review. The last local query still executed at zero budget. Agent, policy and reviewer tokens were zero in this offline example. Utility and security were null because no benchmark evaluator ran.

`python -m examples.policy_failure_cases --output <local-file>` reproduced two constructed limitations. With k=0, a legitimate intended email was blocked after a requested escalation. In the other case, a wrong-object get_file_by_id call executed under the local-query allow-list. Both observations are asserted by tests/test_failure_examples.py. The diagnostic failure labels remain outside the policy request.

The added authorisation tests check direct prohibitions, the single-recipient restriction including bcc, conditional/indirect wording that remains review work, resistance to permission claims in tool history, and unchanged decisions across budgets. Gate tests confirm that direct user-scope denials preserve the review budget and never execute the blocked tool.

## Interpretation

The tests establish the behaviour of the rules and gate interface on these inputs. They do not show live task completion, attack success, real reviewer accuracy, formal TCR@k, or dollar cost. The wrong-object example documents a real limit of operation-based approval rather than claiming full authorisation checking. The credential rule also has documented coverage limits.

The existing workspace replay remains a connection test. Ground-truth calls are used only by that existing scripted harness, not by the policy. Real model, reviewer and attack configuration are still shared experiment dependencies. The report and presentation describe this boundary and do not turn local logs into formal results.

The shared full-approve and nested-call behaviour is unchanged. Selected tasks needing nested calls require a baseline caveat in the formal experiment description. Late-reviewer-cost semantics remain those of the original shared gate.
