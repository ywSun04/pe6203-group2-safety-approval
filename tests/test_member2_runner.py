"""Offline runner checks; all HTTP responses are simulated, never benchmark evidence."""
import json
from types import SimpleNamespace

import httpx
import pytest
from agentdojo.task_suite.load_suites import get_suite
from experiments import run_suite as runner


@pytest.mark.parametrize('raw,attacked,expected', [
    (True, True, False), (False, True, True), (True, False, True),
])
def test_security_orientation(raw, attacked, expected):
    assert runner.security_passed(raw, attacked) is expected


def test_preflight_does_not_construct_model(monkeypatch, tmp_path):
    import openai
    def forbidden(*args, **kwargs):
        raise AssertionError('No model client during preflight')
    monkeypatch.setattr(openai, 'OpenAI', forbidden)
    assert runner.main(['--k', '0', '--log-dir', str(tmp_path)]) == 0
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize('extra', [
    ['--k', '-1'], ['--repeat', '0'], ['--max-agent-requests', '0'],
    ['--attack', 'file'], ['--injection-task', 'injection_task_0'],
    ['--reviewer-timeout', '0'], ['--reviewer-timeout', 'nan'],
    ['--connect-timeout', '0'], ['--connect-timeout', 'inf'],
])
def test_invalid_plan_rejected(extra, tmp_path):
    with pytest.raises(SystemExit):
        runner.parse_args(['--k', '0', '--log-dir', str(tmp_path), *extra])


def test_agent_request_cap_prevents_http():
    def forbidden(**kwargs):
        raise AssertionError('Request cap must block before HTTP')
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=forbidden)))
    agent = runner.MeasuredAgent(client, 'test', 0, 10)
    with pytest.raises(RuntimeError, match='cap'):
        agent.query('task', None, None, [], {})


def test_missing_usage_is_unknown(tmp_path):
    ledger = runner.UsageLedger(tmp_path/'usage.jsonl', 'test', 'reviewer')
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={})),
                         event_hooks={'request': [ledger.request], 'response': [ledger.response]})
    with client:
        client.get('https://mock.invalid')
    rows = list(map(json.loads, (tmp_path/'usage.jsonl').read_text().splitlines()))
    assert rows[1]['usage_known'] is False
    assert rows[1]['total_tokens'] is None


@pytest.mark.parametrize('existing,expected', [(30, 2), (0.5, 0.5), (None, 2)])
def test_connect_cap_preserves_other_timeouts(tmp_path, existing, expected):
    ledger = runner.UsageLedger(tmp_path/'usage.jsonl', 'test', 'reviewer', connect_timeout=2)
    request = httpx.Request('POST', 'https://mock.invalid', extensions={
        'timeout': {'connect': existing, 'read': 29.5, 'write': 29.5, 'pool': 29.5}})
    ledger.request(request)
    assert request.extensions['timeout'] == {
        'connect': expected, 'read': 29.5, 'write': 29.5, 'pool': 29.5}


def test_injection_file_validation(tmp_path):
    path = tmp_path/'attack.json'
    path.write_text('{"not-a-vector": "payload"}')
    args = runner.parse_args(['--k', '0', '--log-dir', str(tmp_path), '--attack', 'file',
                              '--attack-file', str(path), '--injection-task', 'injection_task_0'])
    suite = get_suite('v1.2.2', 'workspace')
    with pytest.raises(ValueError, match='unknown injection vectors'):
        runner.attack_settings(args, suite)


@pytest.mark.parametrize('policy', ['full-approve', 'full-escalate'])
def test_sdk_to_gate_to_suite_offline(monkeypatch, tmp_path, policy):
    """Task ground-truth replay is test data only, not live agent evaluation."""
    import openai
    suite = get_suite('v1.2.2', 'workspace')
    task = suite.get_user_task_by_id('user_task_0')
    env = task.init_environment(suite.load_and_inject_default_environment({}))
    calls = list(task.ground_truth(env))
    index = 0
    captured = []
    def respond(request):
        nonlocal index
        data = json.loads(request.content)
        assert request.extensions['timeout']['connect'] == 2
        captured.append(data)
        if data['model'] == 'reviewer-test':
            message = {'role': 'assistant', 'content': '{"decision":"APPROVE","reason":"test"}'}
            finish = 'stop'
        elif index < len(calls):
            call = calls[index]
            index += 1
            message = {'role': 'assistant', 'content': None, 'tool_calls': [{
                'id': f'call_{index}', 'type': 'function', 'function': {
                    'name': call.function, 'arguments': json.dumps(call.args)}}]}
            finish = 'tool_calls'
        else:
            message = {'role': 'assistant', 'content': task.GROUND_TRUTH_OUTPUT}
            finish = 'stop'
        return httpx.Response(200, json={'id': 'mock', 'object': 'chat.completion',
            'created': 0, 'model': data['model'], 'choices': [
                {'index': 0, 'message': message, 'finish_reason': finish}],
            'usage': {'prompt_tokens': 5, 'completion_tokens': 2, 'total_tokens': 7}})
    real_client = openai.OpenAI
    def fake_client(**kwargs):
        old = kwargs['http_client']
        kwargs['http_client'] = httpx.Client(transport=httpx.MockTransport(respond),
                                            event_hooks=old.event_hooks)
        old.close()
        return real_client(**kwargs)
    monkeypatch.setattr(openai, 'OpenAI', fake_client)
    for key, value in {'OPENAI_COMPATIBLE_BASE_URL': 'https://mock.invalid/v1',
                       'OPENAI_COMPATIBLE_API_KEY': 'not-a-real-key',
                       'REVIEWER_MODEL': 'reviewer-test', 'REVIEWER_API_KEY': 'not-a-real-key',
                       'REVIEWER_BASE_URL': 'https://mock.invalid/v1'}.items():
        monkeypatch.setenv(key, value)
    command = ['--live', '--k', '20', '--policies', policy, '--log-dir', str(tmp_path)]
    assert runner.main(command) == 0
    directory = next(tmp_path.iterdir())
    row = json.loads((directory/'tasks.jsonl').read_text())
    assert row['task_completed'] is True
    assert row['tokens']['agent'] == 7*(len(calls)+1)
    reviews = len(calls) if policy == 'full-escalate' else 0
    assert row['actual_escalation_count'] == reviews
    assert row['tokens']['reviewer'] == 7*reviews
    assert json.loads((directory/'summary.json').read_text())['attack_success'] is None
    assert (directory/'trajectory.jsonl').exists()
    assert 'not-a-real-key' not in ''.join(p.read_text() for p in directory.iterdir())
    assert all('ground_truth' not in payload for payload in captured)
    first_id = row['run_id']
    index = 0
    assert runner.main(command) == 0
    assert len(list(tmp_path.iterdir())) == 2
    assert all(p.name != first_id for p in tmp_path.iterdir() if p != directory)
