"""Register an observed supplement snapshot, without changing original IDs."""
import argparse
import csv
import importlib.util
import json
from pathlib import Path
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from evaluation import evaluate
from evaluation.reconciliation import canonical_profile,json_sha,FROZEN_COMMIT,PROTOCOL


def write_dict(path,value):
    # Keep one UUID entry per line so the sidecar is reviewable in a PR.
    body=',\n'.join('  '+json.dumps(k)+': '+json.dumps(v) for k,v in value.items())
    Path(path).write_bytes(('{\n'+body+'\n}\n').encode())


def register(snapshot,evidence,output,confirmation=None):
    snapshot=Path(snapshot);output=Path(output);output.mkdir(parents=True,exist_ok=False)
    rows=list(csv.DictReader((snapshot/'run-ledger.csv').open(encoding='utf-8',newline='')))
    if confirmation is None and any(r.get('mapping_confirmation_status')=='CONFIRMED_BY_EXPLICIT_USER_MESSAGE' for r in rows):
        raise ValueError('Confirmed mapping rows require their explicit confirmation sidecar')
    selected=[r for r in rows if r['role']=='primary_formal' and r['same_profile_eligible']=='True']
    with zipfile.ZipFile(evidence) as z:catalog=json.loads(z.read('source-catalog.json'))
    confirmed={}
    if confirmation is not None:
        confirm_spec=importlib.util.spec_from_file_location('mapping_confirmation',ROOT/'analysis/member5-supplement/confirm_mapping.py')
        confirmmod=importlib.util.module_from_spec(confirm_spec);confirm_spec.loader.exec_module(confirmmod)
        declaration=json.loads(Path(confirmation).read_text(encoding='utf-8-sig'))
        review=ROOT/'evidence/member6-supplement-20261031/M6_305_Mapping_Review.csv'
        confirmed=confirmmod.validate_confirmation(declaration,review.read_bytes())
        if not confirmed.keys()<={r['run_id'] for r in rows}:raise ValueError('Confirmed mapping rows are missing')
        for r in rows:
            if r['run_id'] in confirmed:confirmmod.bind_row(r,confirmed[r['run_id']])
    spec=importlib.util.spec_from_file_location('supplement_plan',ROOT/'scripts/member5_experiment_plan.py')
    planmod=importlib.util.module_from_spec(spec);spec.loader.exec_module(planmod)
    plan=planmod.build_plan(ROOT/'configs/member5/experiment-plan.json',ROOT,
        evidence_kind='formal',integration_commit=FROZEN_COMMIT)
    expected={(r['task_id'],r['runner_policy'],r['k'],r['repetition'],r['condition']):r for r in plan['evaluation_plan']}
    registry={};observed=[];directories=[]
    for r in selected:
        directory=snapshot/'raw-run-files'/r['run_id']
        m=json.loads((directory/'manifest.json').read_text(encoding='utf-8-sig'));s=m['settings']
        key=(r['task_id'],r['policy'],int(r['k']),int(r['mapped_repetition']),r['condition'])
        row=dict(expected[key]);row.update(run_id=r['run_id'],matched=True)
        signature=json_sha(canonical_profile(s));row['configuration_signature']=signature[:16]
        entry={k:row[k] for k in ['evidence_kind','experiment_id','suite','suite_version','model_id','reviewer_model',
            'condition','attack_id','attack_sha256','attack_pack_id','attack_pack_sha256','repetition']}
        original=catalog['runs'][r['run_id']]
        reference=('evidence/member6-supplement-20261031/m6_target_rep_logs.zip!'+original['source_manifest']
            if original['source_archive']=='m6_target_rep_logs.zip'
            else 'evidence/member5-received-20261031.zip!runs/'+r['run_id']+'/manifest.json')
        entry['security_scope']='benchmark_goal'
        entry['reconciliation']={'protocol':PROTOCOL,'run_id':r['run_id'],
            'raw_manifest_sha256':r['raw_manifest_sha256'],'raw_repetition':m['repetition'],
            'planned_repetition':int(r['mapped_repetition']),'raw_profile_sha256':json_sha(planmod.normalized(s)),
            'canonical_profile_sha256':signature,'owner_acknowledged':r['run_id'] in confirmed,
            'evidence_refs':[reference,'results/member5-supplement-20261031/mapping-confirmation.json' if r['run_id'] in confirmed
                else 'M6 mapping acknowledgement remains pending' if r['mapping_owner_ack_required']=='True'
                else 'Original raw repetition; no remapping required']}
        registry[r['run_id']]=entry;observed.append(row);directories.append(directory)
    result=evaluate(directories,registry=registry,plan=observed)
    assert len(selected)==len(registry)==len(observed)==1054
    assert not result['warnings'],result['warnings']
    write_dict(output/'registry.json',registry)
    (output/'observed-evaluation-plan.json').write_bytes(('[\n'+',\n'.join(json.dumps(r) for r in observed)+'\n]\n').encode())
    summary={'observed_primary_runs':len(selected),'warnings':result['warnings'],'groups':result['groups'],
        'denominator':'Only received same-profile selected primary positions.',
        'mapping_owner_ack_pending':sum(r['mapping_owner_ack_required']=='True' and r['run_id'] not in confirmed for r in selected),
        'mapping_owner_ack_confirmed':sum(r['run_id'] in confirmed for r in selected),
        'security_scope':'benchmark_goal; strict TCR is supplied separately by the executed-action audit.'}
    (output/'standard-evaluation-summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'observed_primary_runs':len(selected),'standard_evaluation_warnings':result['warnings']}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['snapshot','evidence','output']:p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--confirmation',type=Path)
    a=p.parse_args();register(a.snapshot,a.evidence,a.output,a.confirmation)
