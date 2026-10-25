# Member 3 basic risk policy

## What is included

Member 3 supplies `BasicRiskPolicy` in `approval_gate/policies/basic_risk.py`. The class exposes `decide(request)` and returns exactly `decision` and `reason`. The allowed decisions are `APPROVE`, `DENY`, and `ESCALATE`. Each reason starts with a stable rule ID. The gate already records that reason, so this module does not change the shared log format.

The module is a fixed, conservative routing baseline. It does not call a model or a reviewer. `last_token_usage` is always zero. It does not read benchmark labels, ground-truth actions, task objects, or environment objects. Its runtime code uses the Python standard library only.

The handoff follows the README and contract at repository commit `5eb4f9237ef271ac03daacbfea18199b32fadb50`, together with the group's messages requiring a callable module, examples, passing tests, and dependency instructions. That main revision does not contain `docs/module-intake.md` or a single-task CLI. This contribution does not invent or replace those shared interfaces. Member 2 still owns the experiment entry point and must call `build_approval_pipeline`.

## Interface

The input requires `user_task` as a non-empty string, `tool_name` as a non-empty string, `tool_arguments` as a JSON-compatible dictionary, and `remaining_budget` as a non-negative integer. `history` and `tool_metadata` are optional. This baseline does not use either to lower risk. It also ignores unexpected top-level fields rather than inspecting any private context placed there. The shared gate remains responsible for sanitising public context.

```python
from approval_gate.contract import build_request, parse_policy_output
from approval_gate.policies import BasicRiskPolicy

policy = BasicRiskPolicy()
request = build_request(
    user_task="Find the project notes.",
    tool_name="search_files",
    tool_arguments={"query": "project notes"},
    remaining_budget=0,
)
result = policy.decide(request)
assert parse_policy_output(result)[0] == "APPROVE"
```

The policy never mutates the request and keeps no cross-task state. `remaining_budget` is validated but does not change its risk decision. A risky call still returns `ESCALATE` when the budget is zero. The gate then denies the call without invoking a reviewer. A direct low-impact query can still run. The policy must not turn an exhausted escalation into an approval.

## Rules and evidence

R0 denies a malformed request. It also rejects non-JSON arguments, non-finite numbers, excessive nesting, and oversized inputs. The limits are 16 argument-container levels, 4,096 visited argument nodes, and 100,000 combined text characters, including the task, tool name, keys, and string values. These are local processing limits, not review-budget thresholds. The traversal is iterative so a cyclic direct input cannot cause an unbounded recursive walk. These limits do not validate the full tool schema; AgentDojo remains responsible for executing schema-valid tools.

R1 denies a narrow class of explicit credential egress. It checks transmitted text fields for a literal password/key/token assignment or a private-key header. It also checks outbound URL strings and structured attachment content. The rule normalises full-width Unicode forms. It does not scan the user's task or arbitrary history for a keyword and call that an attack. A plain discussion of password resets is not enough to trigger this denial. The rule is a proposed hard policy of this baseline, not a statement that AgentDojo requires this particular pattern. It may block legitimate quoted credential examples, and it will not recognise all secrets, encodings, or attachment contents. Every other known outbound action still goes to review. A stable reason does not echo the matched value, although the shared gate logs complete tool arguments. Use synthetic credentials in tests and protect real logs.

R2 approves only exact names in the reviewed `LOCAL_QUERIES` set. These include local file searches, calendar searches, contact/email lookups, channel reads, and travel-information queries. This is not a general permission check. A query can still reveal information to the agent or create risk later. The baseline relies on the selected task environment for object-level read permissions and reviews subsequent external or state-changing actions. It must not be described as preventing all prompt injection or information exposure.

R3 escalates account, identity, financial, and arbitrary-filesystem reads. The tool list includes `get_user_information`, `get_user_info`, `get_iban`, balance/transaction queries, and `read_file`. A read verb alone does not prove low impact.

R4 escalates recipient, audience, and network actions. It includes email, sharing, Slack messages/invitations, calendar invitations, webpage access/publication, and downloads. An HTTP-style GET can carry sensitive values in its URL, so `get_webpage` is not in the local-query allow-list. The reviewer must check the target and task context.

R5 escalates transfers, transaction scheduling/updates, and reservations. This baseline does not invent a safe monetary amount. A small transfer or an explicitly requested reservation still requires review.

R6 escalates deletion, account changes, file writes, calendar changes, and unread-email access. The pinned implementation of `get_unread_emails` marks messages as read. It therefore belongs here rather than in R2. This is an observable state change in the source, not a guess from the name (AgentDojo Contributors, “email_client.py”).

R7 escalates a tool without a reviewed profile. A name beginning with `get_` or `read_`, or a description that claims the call is safe, does not make it approved. In the full gate, an unregistered tool is blocked before the policy is called. R7 concerns a registered tool that has not yet been profiled, or a direct policy call outside that gate.

Rule order is validation, credential egress, exact reviewed profile, then unknown. The decision does not depend on task wording for semantic authorisation. `user_task` is validated and passed to the reviewer by the gate, but the baseline does not try to infer whether a recipient, amount, or object was requested. That is a limitation, not an unstated task-intent detector. It also means a legitimate write may need review and may fail at a small review budget. Official experiments must measure that utility cost rather than claiming success from unit tests.

## Relation to Member 6

`BasicRiskPolicy` is an independently callable strategy for comparison. `assess_request(request)` exposes the same fixed `RiskAssessment` without spending budget. Member 6 may reuse this assessment or submit a separate strategy, but must document that choice and use a different `name`. Do not overwrite this baseline or relabel it as budget-aware. Both strategies must use the same task set, model, attacks, and k settings when compared. Only the gate resets and decrements the budget.

## Gate connection

```python
from approval_gate.executor import ApprovalGatedToolsExecutor
from approval_gate.pipeline import build_approval_pipeline
from approval_gate.policies import BasicRiskPolicy
from approval_gate.records import GateLogger

# config and real_reviewer are supplied by Members 2 and 4.
gate = ApprovalGatedToolsExecutor(
    policy=BasicRiskPolicy(),
    reviewer=real_reviewer,
    gate_logger=GateLogger("logs/experiment"),
    k=3,
)
pipeline = build_approval_pipeline(config, gate, config_id="member3-basic-v1")
# The experiment runner calls start_task once, runs the task, then finish_task.
```

This is a connection snippet, not a runnable experiment with hidden defaults. The reviewer, model configuration, suite version, tasks, attacks, and official output path remain the experiment team's choices. The module does not load evaluation answers to make decisions. `examples/member3_gate_smoke.py` provides a fully runnable offline connection check with fake local tools and `FakeReviewer`.

## Install and run

Use the group's source commit `089ed468cf3ed0322acc66b0211f26d9d90dbf60`. `requirements.txt` already pins it. The source package still reports distribution version `0.1.35`; check `direct_url.json` through the supplied script rather than using the version number as proof of the source. Do not replace the VCS requirement with `agentdojo==0.1.35`.

From the repository root on Windows, create an isolated environment and install the pinned runtime and test dependencies. The temporary directory is kept inside that checkout to avoid restricted system temporary paths. The Git setting is scoped to this terminal process; it does not change the global Git configuration.

```powershell
py -3.11 -m venv .venv
New-Item -ItemType Directory -Force .venv/install-tmp | Out-Null
$env:TEMP = (Resolve-Path .venv/install-tmp).Path
$env:TMP = $env:TEMP
$env:GIT_CONFIG_COUNT = '1'
$env:GIT_CONFIG_KEY_0 = 'core.longpaths'
$env:GIT_CONFIG_VALUE_0 = 'true'
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-dev.txt
.\.venv\Scripts\python.exe scripts/check_member3_environment.py
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m examples.member3_policy
.\.venv\Scripts\python.exe -m examples.member3_gate_smoke --log-dir logs/member3-smoke
```

If `py` is not installed, use an available Python 3.11 interpreter for the first line. The tested local environment used Python 3.11.9. No API key or model configuration is needed for these checks. The runtime dependency pin is unchanged. `requirements-dev.txt` adds pytest only. On Linux/macOS use the corresponding `.venv/bin/python` commands; the Windows temporary-path workaround is not normally needed.

## Validation and logs

Policy tests cover operation routing, literal credential cases, benign discussions, malicious optional context, malformed inputs, state/budget independence, and processing bounds. Gate tests verify actual execution/no-execution and the call/task records. They check a shared budget across turns, per-task reset, reviewer-denial cost, an exhausted escalation that does not count as actual review, and a direct query still running at zero.

The offline smoke script uses fake functions named `search_files` and `send_email`. It does not send mail or run a model. It writes `task_completed` and `security_passed` as null because no benchmark evaluator ran. Logs are generated under the chosen local directory and are not committed as experimental data. The late-reviewer-cost accounting and nested-call handling remain owned by the shared gate; this module does not alter either. Member 5 can use existing `policy_reason` rule IDs and `policy_name=basic_risk_v1` without new log fields.

The original workspace ground-truth replay is an existing connection test. It is not consulted by the policy and must not be presented as a new security evaluation. Actual counts and commands from this handoff are recorded in `docs/member3-validation.md` after execution.

## Works Cited

AgentDojo Contributors. “email_client.py.” *AgentDojo*, commit 089ed468cf3ed0322acc66b0211f26d9d90dbf60, https://github.com/ethz-spylab/agentdojo/blob/089ed468cf3ed0322acc66b0211f26d9d90dbf60/src/agentdojo/default_suites/v1/tools/email_client.py. Accessed 26 Oct. 2026.

AgentDojo Contributors. “Tools.” *AgentDojo*, commit 089ed468cf3ed0322acc66b0211f26d9d90dbf60, https://github.com/ethz-spylab/agentdojo/tree/089ed468cf3ed0322acc66b0211f26d9d90dbf60/src/agentdojo/default_suites/v1/tools. Accessed 26 Oct. 2026.

“Approval Gate.” *PE6203 Group 2 Safety Approval*, README.md and approval_gate/contract.py, commit 5eb4f9237ef271ac03daacbfea18199b32fadb50, https://github.com/ywSun04/pe6203-group2-safety-approval. Accessed 26 Oct. 2026.

The source explains tool effects and the shared interface. The rule grouping, credential pattern, and processing limits are Member 3 design choices. Tests use constructed examples, not hidden attack annotations. Codex assisted with implementation, source inspection and test preparation; no formal experiment results are claimed.
