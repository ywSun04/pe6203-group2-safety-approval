"""Join an immutable 196-run supplement to the previous received snapshot.

The review CSV is evidence about its stated status, not an owner signature
inferred from delivery. No original manifest or repetition is rewritten.
"""
import argparse
from collections import Counter
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from evaluation.reconciliation import canonical_profile,json_sha

FILES={'manifest.json','calls.jsonl','tasks.jsonl','usage.jsonl','summary.json','trajectory.jsonl'}


def sha(value):return hashlib.sha256(value).hexdigest()
def csv_rows(raw):return list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))


def review_table(supplied,expected,fields):
    """Require a complete UUID bijection and unchanged reviewed identity."""
    actual={r['run_id']:r for r in supplied};reference={r['run_id']:r for r in expected}
    if len(actual)!=len(supplied) or len(reference)!=len(expected) or actual.keys()!=reference.keys():
        raise ValueError('Review table UUID coverage differs from the proposed mapping')
    for rid,row in actual.items():
        if any(row.get(k)!=reference[rid].get(k) for k in fields):
            raise ValueError('Review changed an identity or source hash: '+rid)
    statuses=Counter(r.get('review_status','not_supplied') for r in supplied)
    return {'matched_rows':len(actual),'statuses':dict(statuses),
            'owner_confirmation_established':bool(supplied) and all(r.get('review_status')=='CONFIRMED_BY_OWNER' for r in supplied)}


def intake(old_evidence,raw_supplement,mapping_review,exclusions_review,output):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    prior=ROOT/'results/member5-final-20261031'
    expected=csv_rows((prior/'pending-raw196-candidates.csv').read_bytes())
    expected_ids={r['run_id'] for r in expected};expected_by_id={r['run_id']:r for r in expected}
    meta=json.loads((prior/'pending-raw196.json').read_text(encoding='utf-8-sig'))
    raw_supplement=Path(raw_supplement)
    assert sha(raw_supplement.read_bytes())==meta['expected_sha256']
    old_payload={}
    with zipfile.ZipFile(old_evidence) as z:
        catalog=json.loads(z.read('source-catalog.json'))
        for i in z.infolist():
            if not i.is_dir() and i.filename!='source-catalog.json':old_payload[i.filename]=z.read(i)
    old_ids=set(catalog['runs']);new_ids=set();new_rows=[]
    with zipfile.ZipFile(raw_supplement) as z:
        infos=z.infolist();names={i.filename for i in infos}
        assert len(names)==len(infos) and sum(i.file_size for i in infos)<30_000_000
        assert all(i.file_size<5_000_000 for i in infos)
        assert z.testzip() is None
        for name in sorted(names):
            if not name.endswith('/manifest.json'):continue
            raw=z.read(name);m=json.loads(raw.decode('utf-8-sig'));rid=m['run_id'];s=m['settings']
            assert re.fullmatch(r'\d{8}T\d{6}Z-[a-f0-9]{32}',rid)
            assert rid not in old_ids|new_ids and rid in expected_ids
            new_ids.add(rid)
            proposed=expected_by_id[rid]
            assert (m['task_id'],s['policy'],s['k'],m['repetition'],s['attack']) == (
                proposed['task_id'],'budget_aware',int(proposed['k']),int(proposed['repetition']),'none')
            assert m['config_id']==json_sha(s)[:20]
            assert json_sha(canonical_profile(s))[:16]=='ed94c6d6374d08d4'
            files={}
            for filename in FILES:
                data=z.read(name.rsplit('/',1)[0]+'/'+filename)
                old_payload[f'runs/{rid}/{filename}']=data;files[filename]=sha(data)
            catalog['runs'][rid]={'owner':'Member 6','source_archive':'m6_target_rep_logs.zip',
                'source_manifest':name,'files_sha256':files,
                'copies':[{'archive':'m6_target_rep_logs.zip','manifest':name}],'is_original_smoke':False}
            new_rows.append({'run_id':rid,'task_id':m['task_id'],'k':s['k'],
                'raw_repetition':m['repetition'],'raw_manifest_sha256':sha(raw),
                'same_profile_signature':'ed94c6d6374d08d4','required_companion_files':6})
    assert new_ids==expected_ids and len(new_ids)==196
    catalog['sources_sha256']['m6_target_rep_logs.zip']=sha(raw_supplement.read_bytes())
    supplied_mapping=csv_rows(Path(mapping_review).read_bytes())
    expected_mapping=csv_rows((prior/'m6-mapping-confirmation-needed.csv').read_bytes())
    map_check=review_table(supplied_mapping,expected_mapping,list(expected_mapping[0]))
    supplied_exclusions=csv_rows(Path(exclusions_review).read_bytes())
    expected_exclusions=csv_rows((prior/'configuration-exclusions.csv').read_bytes())
    exclusion_check=review_table(supplied_exclusions,expected_exclusions,list(expected_exclusions[0]))
    old_payload['source-catalog.json']=(json.dumps(catalog,indent=2)+'\n').encode()
    archive=output/'combined-evidence.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for name,data in sorted(old_payload.items()):
            info=zipfile.ZipInfo(name,date_time=(2026,10,31,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
            z.writestr(info,data)
    with (output/'new196-raw-verification.csv').open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(new_rows[0]),lineterminator='\n');writer.writeheader();writer.writerows(new_rows)
    result={'prior_raw_UUIDs':len(old_ids),'new_raw_UUIDs':len(new_ids),'combined_raw_UUIDs':len(catalog['runs']),
        'new_UUID_overlap':0,'new196_matches_previous_candidate_list':True,
        'new196_source_archive_matches_expected_sha256':True,
        'combined_evidence_sha256':sha(archive.read_bytes()),'mapping_review':map_check,
        'exclusions_review':{'matched_rows':exclusion_check['matched_rows'],
            'handling':dict(Counter(r['handling'] for r in supplied_exclusions)),
            'cause_of_endpoint_change_explained':False,'quarantine_retained':True},
        'source_hashes':{Path(p).name:sha(Path(p).read_bytes()) for p in [raw_supplement,mapping_review,exclusions_review]},
        'new_model_API_calls':0,'original_records_edited':False}
    (output/'intake-check.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['old-evidence','raw-supplement','mapping-review','exclusions-review','output']:
        p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();print(json.dumps(intake(a.old_evidence,a.raw_supplement,a.mapping_review,a.exclusions_review,a.output),indent=2))
