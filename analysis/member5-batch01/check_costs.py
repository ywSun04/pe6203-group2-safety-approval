"""Independently reconcile saved batch token and HITL records without API calls.

Writes to a new output directory and exits nonzero on accounting discrepancies.
"""
from pathlib import Path
import argparse
import json, csv
from collections import defaultdict, Counter
from decimal import Decimal

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--batch-root',type=Path,required=True,help='Extracted batch directory containing logs and packaged evaluation.')
parser.add_argument('--output',type=Path,required=True,help='New directory for this independent audit; existing directories are rejected.')
args=parser.parse_args()
ROOT=args.batch_root.resolve()
OUT=args.output.resolve()
if not ROOT.is_dir():parser.error(f'Batch root is not a directory: {ROOT}')
if not (ROOT/'logs').is_dir():parser.error('Batch root must contain logs/')
if OUT.exists():parser.error(f'Output directory already exists: {OUT}')
if OUT==ROOT or OUT.is_relative_to(ROOT):parser.error('Output must be outside the source batch directory')
def read(p): return json.loads(p.read_text(encoding='utf-8-sig'))
def rows(p):
    return [json.loads(x) for x in p.read_text(encoding='utf-8-sig').splitlines() if x.strip()] if p.exists() else []

allrows=[]; issues=[]; events=[]
for path in sorted((ROOT/'logs').rglob('manifest.json')):
    d=path.parent;m=read(path);taskrows=rows(d/'tasks.jsonl');callsrows=rows(d/'calls.jsonl');usage=rows(d/'usage.jsonl');summary=read(d/'summary.json')
    assert len(taskrows)==1, str(path)
    task=taskrows[0]; rid=m['run_id'];settings=m['settings']
    calls=[r for r in callsrows if r['record_type']=='tool_call'];late=[r for r in callsrows if r['record_type']=='late_reviewer_usage']
    actual=sum(r['actually_escalated'] is True for r in calls);requested=sum(r['requested_escalation'] is True for r in calls)
    if actual!=task['actual_escalation_count'] or requested!=task['requested_escalation_count']:issues.append((rid,'review count mismatch'))
    before=task['k']
    for c in calls:
        if c['budget_before']!=before:issues.append((rid,c['call_id'],'discontinuous budget'))
        before-=int(c['actually_escalated'])
        if c['budget_after']!=before:issues.append((rid,c['call_id'],'budget mismatch'))
    for r in taskrows+callsrows+usage:
        if r.get('run_id')!=rid:issues.append((rid,'run id mismatch'))
    attempts={};responses={}
    for row in usage:
        key=(row['component'],row['attempt']);target=attempts if row['record_type']=='api_attempt' else responses
        if key in target:issues.append((rid,key,'duplicate ledger row'))
        target[key]=row
    unknown=[]
    tokens=defaultdict(int);cost=defaultdict(Decimal);cost_known=Counter();cost_unknown=Counter()
    for key in attempts.keys()|responses.keys():
        res=responses.get(key)
        if res is None or res.get('usage_known') is not True or not isinstance(res.get('total_tokens'),int):unknown.append(key)
        else:tokens[key[0]]+=res['total_tokens']
        if res is not None and isinstance(res.get('provider_cost'),(int,float,str)):
            cost[key[0]]+=Decimal(str(res['provider_cost']));cost_known[key[0]]+=1
        else:cost_unknown[key[0]]+=1
    late_excluded=sum(r['late_reviewer_tokens'] for r in late if r['included_in_task_total'] is False)
    late_included=sum(r['late_reviewer_tokens'] for r in late if r['included_in_task_total'] is True)
    expected={**task['tokens']};expected['reviewer']+=late_excluded
    for component in ['agent','policy','reviewer']:
        if tokens[component]!=expected[component]:issues.append((rid,component,'tokens mismatch',tokens[component],expected[component]))
    if sum(r.get('reviewer_retry_count',0) for r in calls)!=task['reviewer_retry_count']:issues.append((rid,'retry count mismatch'))
    if sum(r.get('reviewer_retry_tokens',0) for r in calls)!=task['reviewer_retry_tokens']:issues.append((rid,'retry tokens mismatch'))
    row=dict(run_id=rid,task_id=m['task_id'],policy=task['policy_name'],condition=settings['attack'],repetition=m['repetition'],
      utility_completed=task['task_completed'],benchmark_security_passed=task['security_passed'],attack_success=summary['attack_success'],
      error_type=summary['error_type'],status=summary['status'],actual_reviews=actual,requested_reviews=requested,
      call_count=len(calls),budget_exhausted=sum(r['requested_escalation'] and not r['actually_escalated'] and r['budget_before']==0 for r in calls),
      agent_tokens=expected['agent'],policy_tokens=expected['policy'],reviewer_tokens=expected['reviewer'],
      reviewer_retry_count=task['reviewer_retry_count'],reviewer_retry_tokens=task['reviewer_retry_tokens'],
      late_rows=len(late),late_included_tokens=late_included,late_excluded_tokens=late_excluded,
      api_attempts=len(attempts),api_responses=len(responses),unknown_usage_attempts=len(unknown),
      agent_api_attempts=sum(k[0]=='agent' for k in attempts),reviewer_api_attempts=sum(k[0]=='reviewer' for k in attempts),
      non_200_responses=[r['status'] for r in responses.values() if r['status']!=200],
      policy_decisions=dict(Counter(r['policy_decision'] for r in calls)),
      reviewer_decisions=dict(Counter(r['reviewer_decision'] for r in calls if r['actually_escalated'])),
      deny_reasons=[r['deny_reason'] for r in calls if r['final_decision']=='DENY'],
      provider_cost_agent=str(cost['agent']),provider_cost_reviewer=str(cost['reviewer']),provider_cost_total=str(sum(cost.values())),
      cost_known_responses=sum(cost_known.values()),cost_unknown_attempts=sum(cost_unknown.values()),
      usage_ledger_tokens=dict(tokens),directory=d.relative_to(ROOT).as_posix())
    allrows.append(row)

groups={}
for r in allrows:
    key=(r['policy'],r['condition'])
    if key not in groups:groups[key]=dict(policy=key[0],condition=key[1],runs=0,utility_completed=0,actual_reviews=0,requested_reviews=0,hitl_utility_completed=0,call_count=0,budget_exhausted=0,agent_tokens=0,policy_tokens=0,reviewer_tokens=0,reviewer_retry_count=0,reviewer_retry_tokens=0,late_rows=0,late_included_tokens=0,late_excluded_tokens=0,api_attempts=0,api_responses=0,unknown_usage_attempts=0,technical_run_errors=0,attack_successes=0,provider_cost=Decimal(0))
    g=groups[key];g['runs']+=1;g['utility_completed']+=r['utility_completed'] is True;g['hitl_utility_completed']+=r['actual_reviews'] if r['utility_completed'] else 0
    g['technical_run_errors']+=bool(r['error_type']);g['attack_successes']+=r['attack_success'] is True;g['provider_cost']+=Decimal(r['provider_cost_total'])
    for field in ['actual_reviews','requested_reviews','call_count','budget_exhausted','agent_tokens','policy_tokens','reviewer_tokens','reviewer_retry_count','reviewer_retry_tokens','late_rows','late_included_tokens','late_excluded_tokens','api_attempts','api_responses','unknown_usage_attempts']:g[field]+=r[field]
for g in groups.values():g['provider_cost']=str(g['provider_cost'])

packaged=read(ROOT/'member2-batch01-evaluation/evaluation.json')
actual_packaged=[r for r in packaged['tasks'] if r['observed_task_row']]
assert len(actual_packaged)==len(allrows)==18
packmap={r['run_id']:r for r in actual_packaged}
for r in allrows:
    p=packmap[r['run_id']]
    for field,pfield in [('actual_reviews','actual_escalations'),('requested_reviews','requested_escalations'),('agent_tokens','agent_tokens_recorded'),('policy_tokens','policy_tokens_recorded'),('reviewer_tokens','reviewer_tokens_recorded')]:
        if r[field]!=p[pfield]:issues.append((r['run_id'],'packaged evaluator mismatch',field,r[field],p[pfield]))
result={'runs':allrows,'groups':list(groups.values()),'issues':issues,'packaged_warnings':packaged['warnings']}
OUT.mkdir(parents=True,exist_ok=False)
(OUT/'cost-audit.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
with (OUT/'group-totals.csv').open('w',newline='',encoding='utf-8') as f:
    w=csv.DictWriter(f,fieldnames=list(next(iter(groups.values()))));w.writeheader();w.writerows(groups.values())
print(json.dumps({'groups':list(groups.values()),'issues':issues,'packaged_warnings':packaged['warnings'],'totals':{field:sum(r[field] for r in allrows) for field in ['utility_completed','actual_reviews','requested_reviews','call_count','budget_exhausted','agent_tokens','policy_tokens','reviewer_tokens','reviewer_retry_count','reviewer_retry_tokens','late_rows','api_attempts','api_responses','unknown_usage_attempts']}},indent=2))
raise SystemExit(1 if issues else 0)
