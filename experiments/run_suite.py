"""Pinned AgentDojo experiment runner. Default is an offline preflight; --live opts in."""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import os
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
import sys
import subprocess
import importlib.metadata
import math

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agentdojo.agent_pipeline.agent_pipeline import PipelineConfig
from agentdojo.agent_pipeline.llms.openai_llm import (
    OpenAILLM, _function_to_openai, _message_to_openai, _openai_to_assistant_message,
)
from agentdojo.logging import Logger
from agentdojo.task_suite.load_suites import get_suite
from approval_gate.executor import ApprovalGatedToolsExecutor, _contains_function_call
from approval_gate.pipeline import build_approval_pipeline
from approval_gate.policies import make_policy
from approval_gate.records import GateLogger
from approval_gate.stubs import FullApprove, FullEscalate
from reviewer import LlmReviewer
from reviewer.llm_reviewer import PROMPT_SHA256


def write_row(path, row):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as f:
        f.write(json.dumps(row, ensure_ascii=False, default=str) + '\n')


def source_versions():
    """Record integration state and actual module hashes, without repository URLs."""
    import approval_gate.executor as executor
    import approval_gate.policies.basic_risk as risk
    import approval_gate.policies.budget_aware as budget
    import reviewer.llm_reviewer as reviewer_module
    import agentdojo.task_suite.task_suite as task_suite
    modules = [executor, risk, budget, reviewer_module, task_suite]
    hashes = {m.__name__: hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest() for m in modules}
    git = subprocess.run(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'],
                         capture_output=True, text=True)
    dist = importlib.metadata.distribution('agentdojo')
    direct = json.loads(dist.read_text('direct_url.json') or '{}')
    return dict(integration_commit=git.stdout.strip() if git.returncode == 0 else None,
                agentdojo_commit=direct.get('vcs_info', {}).get('commit_id'),
                module_sha256=hashes,
                versions={name: importlib.metadata.version(name) for name in ['agentdojo', 'openai', 'httpx']})


class UsageLedger:
    """One row per HTTP attempt; missing usage remains explicitly unknown.

    Response hooks also run for SDK-created reviewer clients and late responses.
    Only usage/status are persisted here, never headers or request/response bodies.
    """
    def __init__(self, path, run_id, component, on_tokens=None, connect_timeout=2):
        self.path, self.run_id, self.component = path, run_id, component
        self.on_tokens = on_tokens
        self.connect_timeout = connect_timeout
        self.attempt = 0
        self._lock = threading.Lock()

    def request(self, request):
        # The SDK replaces HTTPX timeout values in with_options(). Apply a cap
        # after that replacement, preserving read/write/pool and reviewer deadline.
        timeout = dict(request.extensions.get('timeout') or {})
        previous = timeout.get('connect')
        timeout['connect'] = min(previous, self.connect_timeout) if previous is not None else self.connect_timeout
        request.extensions['timeout'] = timeout
        with self._lock:
            self.attempt += 1
            attempt = self.attempt
        request.extensions['member2_attempt'] = attempt
        write_row(self.path, dict(record_type='api_attempt', run_id=self.run_id,
                                 component=self.component, attempt=attempt,
                                 connect_timeout_seconds=timeout['connect']))

    def response(self, response):
        response.read()
        try:
            usage = response.json().get('usage') or {}
        except (ValueError, AttributeError):
            usage = {}
        total = usage.get('total_tokens')
        known = type(total) is int and total >= 0
        row = dict(record_type='api_response', run_id=self.run_id,
                   component=self.component,
                   attempt=response.request.extensions.get('member2_attempt'),
                   status=response.status_code, usage_known=known,
                   total_tokens=total if known else None,
                   prompt_tokens=usage.get('prompt_tokens'),
                   completion_tokens=usage.get('completion_tokens'),
                   provider_cost=usage.get('cost'))
        write_row(self.path, row)
        if known and self.on_tokens:
            self.on_tokens(total)


class MeasuredAgent(OpenAILLM):
    """Use pinned serialization, one bounded API attempt per turn, no hidden retries."""
    def __init__(self, client, model, max_requests, max_tokens):
        super().__init__(client, model, temperature=0.0)
        self.name = f'openai-compatible:{model}'
        self.requests, self.max_requests, self.max_tokens = 0, max_requests, max_tokens

    def query(self, query, runtime, env, messages, extra_args):
        from openai import NOT_GIVEN
        if self.requests >= self.max_requests:
            raise RuntimeError('Agent request cap reached')
        self.requests += 1
        completion = self.client.chat.completions.create(
            model=self.model,
            messages=[_message_to_openai(m, self.model) for m in messages],
            tools=[_function_to_openai(t) for t in runtime.functions.values()] or NOT_GIVEN,
            temperature=0.0, max_tokens=self.max_tokens,
        )
        output = _openai_to_assistant_message(completion.choices[0].message)
        return query, runtime, env, [*messages, output], extra_args


class Trajectory(Logger):
    def __init__(self, path, run_id):
        self.path, self.run_id = path, run_id

    def log(self, messages, **kwargs):
        from approval_gate.contract import to_jsonable
        write_row(self.path, dict(run_id=self.run_id, messages=to_jsonable(messages)))

    def log_error(self, *args, **kwargs):
        pass  # Provider exception text can expose credentials or request data.


def security_passed(raw, attacked):
    # In this pinned suite, injection_task.security() tests attacker goal achievement.
    return not raw if attacked else True


def nested_preflight(suite, task):
    """Evaluator-only ground-truth inspection. Never execute or pass calls to the model."""
    try:
        env = task.init_environment(suite.load_and_inject_default_environment({}))
        calls = task.ground_truth(env)
        return {'status': 'checked', 'ground_truth_has_nested':
                any(_contains_function_call(c.args) for c in calls)}
    except Exception as e:
        return {'status': 'unknown', 'error_type': type(e).__name__}


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--live', action='store_true', help='Actually call paid model APIs.')
    p.add_argument('--suite', default='workspace')
    p.add_argument('--suite-version', default='v1.2.2')
    p.add_argument('--tasks', nargs='+', default=['user_task_0'])
    p.add_argument('--policies', nargs='+', choices=['full-approve', 'full-escalate',
                   'basic_risk', 'budget_aware'], default=['full-approve'])
    p.add_argument('--k', type=int, nargs='+', required=True)
    p.add_argument('--repeat', type=int, default=1)
    p.add_argument('--model-id', default='openai/gpt-4o-mini')
    p.add_argument('--log-dir', type=Path, required=True)
    p.add_argument('--max-agent-requests', type=int, default=20)
    p.add_argument('--max-output-tokens', type=int, default=2048)
    p.add_argument('--reviewer-timeout', type=float, default=30,
                   help='Reviewer deadline in seconds; changing it changes config_id.')
    p.add_argument('--connect-timeout', type=float, default=2,
                   help='Cap each HTTP connection attempt, separately from the reviewer deadline.')
    p.add_argument('--attack', choices=['none', 'file'], default='none')
    p.add_argument('--attack-file', type=Path)
    p.add_argument('--injection-task')
    a = p.parse_args(argv)
    if any(k < 0 for k in a.k) or min(a.repeat, a.max_agent_requests, a.max_output_tokens) < 1:
        p.error('Budgets must be nonnegative; repeat and request/token caps must be positive.')
    if not math.isfinite(a.reviewer_timeout) or a.reviewer_timeout <= 0:
        p.error('--reviewer-timeout must be finite and positive.')
    if not math.isfinite(a.connect_timeout) or a.connect_timeout <= 0:
        p.error('--connect-timeout must be finite and positive.')
    if a.attack == 'file' and (not a.attack_file or not a.injection_task):
        p.error('--attack file requires --attack-file and --injection-task.')
    if a.attack == 'none' and (a.attack_file or a.injection_task):
        p.error('Attack settings require --attack file.')
    return a


def select_policy(name):
    if name == 'full-approve':
        return FullApprove()
    if name == 'full-escalate':
        return FullEscalate()
    return make_policy(name)


def attack_settings(args, suite):
    if args.attack == 'none':
        return None, {}
    data = json.loads(args.attack_file.read_text(encoding='utf-8'))
    if not isinstance(data, dict) or not data or any(
        not isinstance(k, str) or not isinstance(v, str) for k, v in data.items()
    ):
        raise ValueError('Attack file must be a nonempty object mapping vector IDs to strings.')
    if set(data) - set(suite.get_injection_vector_defaults()):
        raise ValueError('Attack file contains unknown injection vectors.')
    return suite.get_injection_task_by_id(args.injection_task), data


def run_one(args, suite, task, policy_name, k, repetition, injection_task, injections, preflight):
    from openai import OpenAI
    import httpx
    run_id = f"{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex}"
    directory = args.log_dir / run_id
    directory.mkdir(parents=True, exist_ok=False)
    settings = dict(suite=args.suite, suite_version=args.suite_version,
                    model_id=args.model_id, agent_base_url=os.environ['OPENAI_COMPATIBLE_BASE_URL'],
                    reviewer_model=os.environ['REVIEWER_MODEL'],
                    reviewer_base_url=os.environ.get('REVIEWER_BASE_URL', 'https://api.openai.com/v1'),
                    reviewer_prompt_sha256=PROMPT_SHA256, policy=policy_name, k=k,
                    max_agent_requests=args.max_agent_requests, max_output_tokens=args.max_output_tokens,
                    reviewer_timeout_seconds=args.reviewer_timeout, attack=args.attack,
                    connect_timeout_seconds=args.connect_timeout,
                    attack_sha256=hashlib.sha256(json.dumps(injections, sort_keys=True).encode()).hexdigest(),
                    injection_task=args.injection_task, temperature=0.0,
                    source_versions=source_versions(),
                    runner_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    config_id = hashlib.sha256(json.dumps(settings, sort_keys=True).encode()).hexdigest()[:20]
    (directory / 'manifest.json').write_text(json.dumps(dict(
        run_id=run_id, task_id=task.ID, repetition=repetition, config_id=config_id,
        settings=settings, nested_preflight=preflight,
        evidence='live task run; clean run alone does not establish injection resistance',
    ), indent=2), encoding='utf-8')
    gate = ApprovalGatedToolsExecutor(select_policy(policy_name), None, GateLogger(directory), k=k,
                                      reviewer_timeout_seconds=args.reviewer_timeout)
    ledger_path = directory / 'usage.jsonl'
    agent_usage = UsageLedger(ledger_path, run_id, 'agent', gate.add_agent_tokens,
                              connect_timeout=args.connect_timeout)
    reviewer_usage = UsageLedger(ledger_path, run_id, 'reviewer',
                                 connect_timeout=args.connect_timeout)
    # Reviewer may finish after the task timeout. Its client stays open until process exit;
    # existing gate late_reviewer_usage rows retain their original accounting semantics.
    reviewer_http = httpx.Client(event_hooks={'request': [reviewer_usage.request],
                                             'response': [reviewer_usage.response]})
    gate.reviewer = LlmReviewer(os.environ['REVIEWER_MODEL'], OpenAI(
        api_key=os.environ['REVIEWER_API_KEY'], max_retries=0,
        base_url=settings['reviewer_base_url'], http_client=reviewer_http))
    agent_http = httpx.Client(event_hooks={'request': [agent_usage.request],
                                         'response': [agent_usage.response]})
    client = OpenAI(api_key=os.environ['OPENAI_COMPATIBLE_API_KEY'],
                    base_url=settings['agent_base_url'], max_retries=0, timeout=60,
                    http_client=agent_http)
    agent = MeasuredAgent(client, args.model_id, args.max_agent_requests, args.max_output_tokens)
    pipeline = build_approval_pipeline(PipelineConfig(
        llm=agent, model_id=args.model_id, defense=None, system_message_name=None,
        system_message=None),
        gate, config_id=config_id)
    gate.start_task(run_id, task.ID)
    utility = passed = raw = None
    error_type = None
    started = time.monotonic()
    try:
        with Trajectory(directory / 'trajectory.jsonl', run_id):
            utility, raw = suite.run_task_with_pipeline(pipeline, task, injection_task, injections)
            passed = security_passed(raw, injection_task is not None)
    except Exception as e:
        error_type = type(e).__name__
    finally:
        record = gate.finish_task(utility, passed)
        client.close()
    summary = dict(run_id=run_id, task_id=task.ID, error_type=error_type,
                   status='error' if error_type else 'completed',
                   elapsed_seconds=time.monotonic() - started,
                   raw_benchmark_security=raw,
                   attack_success=raw if injection_task else None,
                   nested_calls_observed=False)
    if gate.gate_logger.calls_path.exists():
        summary['nested_calls_observed'] = any(
            row.get('deny_reason') == 'Nested tool calls are not allowed'
            for row in map(json.loads, gate.gate_logger.calls_path.read_text().splitlines()))
    (directory / 'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps(dict(run_id=run_id, directory=str(directory), **{
        k: record[k] for k in ['task_completed', 'security_passed', 'tokens',
                              'actual_escalation_count']}, error_type=error_type)))
    return error_type is None


def main(argv=None):
    args = parse_args(argv)
    suite = get_suite(args.suite_version, args.suite)
    tasks = [suite.get_user_task_by_id(t) for t in args.tasks]
    injection_task, injections = attack_settings(args, suite)
    preflights = {t.ID: nested_preflight(suite, t) for t in tasks}
    plan = dict(model_id=args.model_id, suite=args.suite, suite_version=args.suite_version,
                tasks=args.tasks, policies=args.policies, k=args.k, repeat=args.repeat,
                attack=args.attack, injection_task=args.injection_task,
                planned_runs=len(tasks)*len(args.policies)*len(args.k)*args.repeat,
                nested_preflight=preflights, live=args.live)
    plan['reviewer_timeout_seconds'] = args.reviewer_timeout
    plan['connect_timeout_seconds'] = args.connect_timeout
    print(json.dumps(plan, indent=2))
    if not args.live:
        print('Preflight only. No API calls. Add --live to run paid models.')
        return 0
    required = ['OPENAI_COMPATIBLE_BASE_URL', 'OPENAI_COMPATIBLE_API_KEY',
                'REVIEWER_MODEL', 'REVIEWER_API_KEY']
    missing = [key for key in required if not os.environ.get(key)]
    if missing:
        print('Missing settings (no model called): ' + ', '.join(missing))
        return 2
    ok = True
    for task, policy, k, repetition in itertools.product(tasks, args.policies, args.k, range(args.repeat)):
        ok = run_one(args, suite, task, policy, k, repetition, injection_task, injections,
                     preflights[task.ID]) and ok
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
