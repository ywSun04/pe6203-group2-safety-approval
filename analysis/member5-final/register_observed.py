"""Register only observed, same-profile primary rows with explicit sidecars.

This does not promote pending running-owner acknowledgements or release a run.
"""
import argparse
import csv
import importlib.util
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from evaluation import evaluate
from evaluation.reconciliation import canonical_profile, json_sha, FROZEN_COMMIT, PROTOCOL


def register(snapshot, output):
    snapshot=Path(snapshot);output=Path(output);output.mkdir(parents=True,exist_ok=False)
    ledger=list(csv.DictReader((snapshot/'run-ledger.csv').open(encoding='utf-8',newline='')))
    selected=[r for r in ledger if r['role']=='primary_formal' and r['same_profile_eligible']=='True']
    spec=importlib.util.spec_from_file_location('observed_plan',ROOT/'scripts/member5_experiment_plan.py')
    planmod=importlib.util.module_from_spec(spec);spec.loader.exec_module(planmod)
    original=planmod.build_plan(ROOT/'configs/member5/experiment-plan.json',ROOT,
        evidence_kind='formal',integration_commit=FROZEN_COMMIT)
    expected={(r['task_id'],r['runner_policy'],r['k'],r['repetition'],r['condition']):r for r in original['evaluation_plan']}
    registry={};observed=[];directories=[]
    for r in selected:
        directory=snapshot/'raw-run-files'/r['run_id']
        m=json.loads((directory/'manifest.json').read_text(encoding='utf-8-sig'));s=m['settings']
        key=(r['task_id'],r['policy'],int(r['k']),int(r['mapped_repetition']),r['condition'])
        row=dict(expected[key]);row.update(run_id=r['run_id'],matched=True)
        signature=json_sha(canonical_profile(s));row['configuration_signature']=signature[:16]
        entry={k:row[k] for k in ['evidence_kind','experiment_id','suite','suite_version','model_id','reviewer_model',
            'condition','attack_id','attack_sha256','attack_pack_id','attack_pack_sha256','repetition']}
        entry['security_scope']='benchmark_goal'
        entry['reconciliation']={'protocol':PROTOCOL,'run_id':r['run_id'],
            'raw_manifest_sha256':r['raw_manifest_sha256'],'raw_repetition':m['repetition'],
            'planned_repetition':int(r['mapped_repetition']),'raw_profile_sha256':json_sha(planmod.normalized(s)),
            'canonical_profile_sha256':signature,'owner_acknowledged':False,
            'evidence_refs':['evidence/member5-received-20261031.zip!runs/'+r['run_id']+'/manifest.json',
                'results/member5-unified-20261030/m6-mapping-review.json' if r['mapping_owner_ack_required']=='True'
                else 'raw_manifest_repetition_and_source_catalog']}
        registry[r['run_id']]=entry;observed.append(row);directories.append(directory)
    result=evaluate(directories,registry=registry,plan=observed)
    assert len(selected)==len(registry)==len(observed)==858
    assert not result['warnings'],result['warnings']
    for name,data in [('registry.json',registry),('observed-evaluation-plan.json',observed),
        ('standard-evaluation-summary.json',{'observed_primary_runs':858,'warnings':result['warnings'],
            'groups':result['groups'],'denominator':'Only received same-profile selected primary slots.',
            'mapping_owner_ack_pending':300,'security_scope':'benchmark_goal; strict TCR is supplied separately by the matched-call audit.'})]:
        (output/name).write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'observed_primary_runs':858,'standard_evaluation_warnings':result['warnings']}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--snapshot',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args();register(a.snapshot,a.output)
