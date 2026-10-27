# Reviewer validation record

Evidence collected locally on 27 October 2026.

- Base repository commit: `3a2d5612284999face1812c1ab925b9c1edfa110`.
- AgentDojo source: `089ed468cf3ed0322acc66b0211f26d9d90dbf60`, verified by `scripts/check_agentdojo.py`.
- Environment: macOS arm64, Python 3.11.18 (also verified on Python 3.12.14 before the final pipeline tests), pytest 9.1.1, openai 3.39.0.
- `python -m pytest -q`: **188 passed in 3.86s**.
- New reviewer tests: 43 adapter/contract/SDK cases and 6 gate/pipeline cases, **49 total**.
- `python -m pip check`: no broken requirements.
- `git diff --check`: passed.
- `python -m compileall -q reviewer examples/reviewer_check.py`: passed.
- Invoking `python -m examples.reviewer_check` without `--live` exits before model setup, as intended.

The mock-HTTP SDK tests cover valid parsing, a server 500 with SDK retries overridden
to zero, and SDK read timeout mapping to the gate's ReviewerTimeout. The gate
cases check actual fake-tool execution, refusal, exhausted budget and token totals.
All external effects are simulated. No live model call, paid request, real email,
formal TCR@k, reviewer accuracy score or API dollar cost is claimed.

Both BasicRiskPolicy and BudgetAwarePolicy were exercised through the complete
approval pipeline using simulated HTTP/tool effects. Two reviews consumed the
shared k=2 budget, one simulated email executed, and the task log recorded 34
synthetic reviewer tokens. The final call was blocked after budget exhaustion.
Python 3.11 dependency compatibility check also passed for all 75 installed packages.

Pending: agree on model/provider;
run the synthetic cases with a real model; then perform the shared AgentDojo run.
Missing provider usage remains unknown even though the shared numeric counter
uses zero as a placeholder. Formal cost reconciliation needs provider records.
