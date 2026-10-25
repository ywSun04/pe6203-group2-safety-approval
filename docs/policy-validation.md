# Risk policy validation record

Validation date: 26 October 2026. Base repository revision: `5eb4f9237ef271ac03daacbfea18199b32fadb50`. AgentDojo source revision: `089ed468cf3ed0322acc66b0211f26d9d90dbf60`. The source revision was checked through installed PEP 610 `direct_url.json`, not inferred from the distribution version. That source still reports version `0.1.35`.

The local environment used Windows, Python 3.11.9, and pytest 9.1.1 in a repository-local virtual environment. The policy uses the standard library and has no API-key requirement. The install keeps the group's original VCS requirement and adds pytest through `requirements-dev.txt`.

## Checks actually executed

`python scripts/check_agentdojo.py` reported a matching source commit. `python -m pip check` reported no broken requirements. These checks verify this installation, not all possible future dependency resolutions.

`python -m pytest tests/test_basic_risk_policy.py tests/test_basic_risk_gate.py -q` passed 70 risk-policy cases. The cases cover fixed risk routing, credential markers, malformed/cyclic input, context that must not become authority, budget independence, and real gate execution with fake local tools/reviewer.

`python -m pytest -q` passed 86 cases in the checkout used here. This includes the existing gate tests and existing scripted workspace replay. The replay uses benchmark ground truth only in its test harness; the new policy never imports it. The total is the actual locally collected suite, not a repetition of an earlier test count in a group message.

`python -m examples.risk_policy` emitted valid two-field policy payloads. A local search at budget zero returned `APPROVE`. An ordinary email returned `ESCALATE`. An email containing a synthetic literal credential returned `DENY`. A deletion at budget zero still returned `ESCALATE`, leaving the final denial to the gate.

`python -m examples.gate_smoke --log-dir <local-smoke-directory>` completed using fake local tools and `FakeReviewer`. It performed no email send or model call. The five tool rows had policy decisions `APPROVE, ESCALATE, ESCALATE, DENY, APPROVE`, final decisions `APPROVE, APPROVE, DENY, DENY, APPROVE`, and review budgets after each call `1, 0, 0, 0, 0`. The task row reported two requested reviews, one actual review, and zero policy/model/reviewer tokens. Utility and security were null because no evaluator ran. The second requested review was rejected by the gate without counting as an actual review. The final direct query still executed.

The smoke log was inspected to verify the tool arguments and reason IDs. The generated log is not committed as benchmark evidence. A reviewer failure, retry cost, or late cost still follows the shared logger's existing semantics; The risk policy does not add or recount it.

## Not claimed

This contribution has not run a live agent model, a real Reviewer, adaptive attacks, or the formal benchmark. It reports no attack success rate, task-completion rate, or claim that the risk rules recognise all injections. Input limits, rule groupings, and the credential pattern are fixed design choices. The module routes writes and uncertain calls to the reviewer; its correctness does not prove the reviewer's correctness.

The full-approve baseline and nested-call semantics remain unchanged. The existing gate rejects nested calls before any policy runs. The experiment configuration must document the resulting distinction from original undefended AgentDojo when selecting tasks.
