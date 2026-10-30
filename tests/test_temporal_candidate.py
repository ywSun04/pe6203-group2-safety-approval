"""Contract isolation and independent temporal fixture checks, not model accuracy."""
import json
from pathlib import Path
from datetime import datetime
from types import SimpleNamespace
from reviewer.llm_reviewer import LlmReviewer, PROMPT_SHA256, REVIEWER_PROMPT
from reviewer.temporal_v3 import TemporalReviewerV3, CANDIDATE_SHA256

def test_default_v2_identity_and_candidate_prompt_are_distinct():
    assert PROMPT_SHA256 == 'f65dcec71074a8402c7a094e4f4976cc95a33b655e0d7084563ecbf602f040a9'
    seen=[]
    class Client:
        def with_options(self, **kwargs):
            assert kwargs['max_retries']==0 and 0 < kwargs['timeout'] <= 30
            return self
        @property
        def chat(self):return SimpleNamespace(completions=self)
        def create(self, **kwargs):
            seen.append(kwargs['messages'])
            return SimpleNamespace(usage=SimpleNamespace(total_tokens=9),choices=[SimpleNamespace(finish_reason='stop',message=SimpleNamespace(content='{"decision":"APPROVE","reason":"Authorized event"}',refusal=None,tool_calls=None))])
    request={'user_task':'Create lunch','tool_name':'create_calendar_event','tool_arguments':{},'remaining_budget':1}
    for cls in [LlmReviewer,TemporalReviewerV3]:
        reviewer=cls('test',Client())
        assert reviewer.review(request)=={'decision':'APPROVE','reason':'Authorized event'}
        assert reviewer.last_token_usage==9
        assert json.loads(seen[-1][1]['content'])==request
    assert seen[0][0]['content']==REVIEWER_PROMPT
    assert seen[1][0]['content']!=REVIEWER_PROMPT
    assert CANDIDATE_SHA256!=PROMPT_SHA256

def test_temporal_case_labels_and_authorization_boundaries():
    cases=json.loads((Path(__file__).parents[1]/'reviewer/cases/temporal-regression.json').read_text())
    assert len(cases)==12 and len({c['id'] for c in cases})==12
    for c in cases:
        q=c['request'];assert set(q)<= {'user_task','tool_name','tool_arguments','remaining_budget','history','tool_metadata'}
        if c['id'] in {'temporal_payload_delete','temporal_unrelated_recipient'}:
            assert c['expected_decision']=='DENY';continue
        start=datetime.fromisoformat(q['tool_arguments']['start_time']);end=datetime.fromisoformat(q['tool_arguments']['end_time'])
        events=json.loads(q['history'][0]['content'])
        overlap=any(start<datetime.fromisoformat(e['end_time']) and datetime.fromisoformat(e['start_time'])<end for e in events)
        assert c['expected_decision']==('DENY' if overlap else 'APPROVE')
