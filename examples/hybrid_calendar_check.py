"""Opt-in, paid development check; never used by the formal suite runner."""
import argparse
import hashlib
import json
import os
import uuid
from pathlib import Path
from examples.reviewer_check import evaluate
from reviewer.hybrid_calendar import HybridCalendarReviewer, PROMPT_SHA256
from reviewer.llm_reviewer import PROMPT_SHA256 as BASE_PROMPT_SHA256

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--cases', type=Path, default=Path(__file__).resolve().parents[1]/'reviewer/cases/hybrid-calendar-development.json')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not args.live:
        parser.error('Add --live to enable paid API requests')
    if args.output.exists() or args.output.with_suffix('.usage.jsonl').exists():
        parser.error('Use fresh output paths; preserve first failures')
    if any(not os.environ.get(k) for k in ['REVIEWER_MODEL','REVIEWER_API_KEY']):
        parser.error('Configure local REVIEWER_MODEL and REVIEWER_API_KEY')
    import httpx
    from openai import OpenAI
    from experiments.run_suite import UsageLedger
    run_id=uuid.uuid4().hex
    ledger=UsageLedger(args.output.with_suffix('.usage.jsonl'),run_id,'reviewer',connect_timeout=2)
    client=OpenAI(api_key=os.environ['REVIEWER_API_KEY'],base_url=os.environ.get('REVIEWER_BASE_URL','https://api.openai.com/v1'),max_retries=0,http_client=httpx.Client(event_hooks={'request':[ledger.request],'response':[ledger.response]}))
    reviewer=HybridCalendarReviewer(os.environ['REVIEWER_MODEL'],client)
    cases=json.loads(args.cases.read_text())
    if len({c['id'] for c in cases})!=len(cases):
        parser.error('Unique case IDs required')
    try:
        rows=evaluate(reviewer,cases,30)
    finally:
        client.close()
    report={'evidence':'Development-only corrected-call replay; not formal AgentDojo TCR','run_id':run_id,'reviewer':reviewer.name,'model':reviewer.model,'scope_prompt_sha256':PROMPT_SHA256,'base_prompt_sha256':BASE_PROMPT_SHA256,'candidate_source_sha256':hashlib.sha256((Path(__file__).resolve().parents[1]/'reviewer/hybrid_calendar.py').read_bytes()).hexdigest(),'cases_sha256':hashlib.sha256(args.cases.read_bytes()).hexdigest(),'timeout_seconds':30,'connect_timeout_seconds':2,'rows':rows,'correct':sum(r['correct'] for r in rows),'total':len(rows)}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(f"Development only: {report['correct']}/{report['total']}")

if __name__=='__main__':
    main()
