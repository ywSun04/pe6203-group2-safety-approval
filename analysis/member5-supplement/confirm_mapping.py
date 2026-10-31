"""Apply an explicit mapping confirmation to derived records, never raw files."""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path

SCOPE={'repetition_mapping','primary_attempt','retry_attempt','cross_member_overlap'}
STATUS='CONFIRMED_BY_EXPLICIT_USER_MESSAGE'


def sha(raw):return hashlib.sha256(raw).hexdigest()


def validate_confirmation(confirmation,review_bytes):
    if confirmation.get('status')!=STATUS:
        raise ValueError('Confirmation must be explicit and recorded with its source')
    if set(confirmation.get('scope',[]))!=SCOPE or not confirmation.get('source_reference'):
        raise ValueError('Missing confirmation scope or source reference')
    if confirmation.get('review_csv_sha256')!=sha(review_bytes):
        raise ValueError('Confirmation is not bound to the supplied review CSV bytes')
    review=list(csv.DictReader(io.StringIO(review_bytes.decode('utf-8-sig'))))
    by_id={r['run_id']:r for r in review}
    ids=confirmation.get('confirmed_run_ids',[])
    if len(by_id)!=len(review) or len(ids)!=len(set(ids)) or set(ids)!=by_id.keys() or confirmation.get('confirmed_row_count')!=len(review):
        raise ValueError('Confirmation UUID coverage is incomplete or duplicated')
    expected=sha(('\n'.join(sorted(ids))+'\n').encode())
    if confirmation.get('confirmed_uuid_set_sha256')!=expected:
        raise ValueError('Confirmation UUID-set fingerprint differs')
    return by_id


def bind_row(row,confirmed):
    for key in ['task_id','policy','k','condition','raw_repetition','mapped_repetition','role','primary_run_id','raw_manifest_sha256']:
        if str(row.get(key))!=str(confirmed.get(key)):
            raise ValueError('Mapping/source identity changed for '+row['run_id']+': '+key)


def write_csv(path,rows):
    with Path(path).open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]),lineterminator='\n')
        writer.writeheader();writer.writerows(rows)


def validate_pending_scope(rows,confirmed_ids):
    pending={r['run_id'] for r in rows if r['mapping_owner_ack_required']=='True'}
    if pending and pending!=set(confirmed_ids):
        raise ValueError('Pending mapping UUIDs differ from the explicit confirmation scope')
    if not pending and any(r.get('mapping_confirmation_status')!=STATUS for r in rows if r['run_id'] in confirmed_ids):
        raise ValueError('A prior closure has no matching recorded confirmation status')


def close_pending(value):
    if isinstance(value,dict):
        if 'mapping_ack_pending_runs' in value:value['mapping_ack_pending_runs']=0
        for child in value.values():close_pending(child)
    elif isinstance(value,list):
        for child in value:close_pending(child)


def apply_confirmation(snapshot,confirmation_path,review_csv):
    snapshot=Path(snapshot);confirmation=json.loads(Path(confirmation_path).read_text(encoding='utf-8-sig'))
    confirmed=validate_confirmation(confirmation,Path(review_csv).read_bytes())
    if len(confirmed)!=305:raise ValueError('This supplement expects exactly 305 mapping-review rows')
    with (snapshot/'run-ledger.csv').open(encoding='utf-8-sig',newline='') as stream:rows=list(csv.DictReader(stream))
    if not confirmed.keys()<={r['run_id'] for r in rows}:raise ValueError('Confirmed raw records are missing from snapshot')
    validate_pending_scope(rows,confirmed)
    count=0
    for row in rows:
        if row['run_id'] in confirmed:
            bind_row(row,confirmed[row['run_id']]);row['mapping_owner_ack_required']='False';count+=1
            row['mapping_confirmation_status']=STATUS
        else:row['mapping_confirmation_status']='NOT_REQUIRED_FOR_RAW_REPETITION'
    write_csv(snapshot/'run-ledger.csv',rows)
    for name in ['descriptive-metrics.csv','matched-four-policy-metrics.csv','matched-k-scan.csv']:
        with (snapshot/name).open(encoding='utf-8-sig',newline='') as stream:groups=list(csv.DictReader(stream))
        for group in groups:
            if 'mapping_ack_pending_runs' in group:group['mapping_ack_pending_runs']='0'
        write_csv(snapshot/name,groups)
    path=snapshot/'summary.json';summary=json.loads(path.read_text(encoding='utf-8-sig'));close_pending(summary)
    summary['mapping_ack_confirmed_runs']=count
    summary['mapping_confirmation_source']=confirmation['source_reference']
    summary['interpretation']='Observed denominators only. All 305 mapped attempt assignments have explicit user-provided confirmation. Strict TCR still requires an executed-action audit. Seven configuration exceptions stay excluded. No new batch is authorized.'
    path.write_bytes((json.dumps(summary,indent=2)+'\n').encode())
    return {'confirmed_rows':count,'confirmed_primary_rows':sum(r['role']=='primary_formal' for r in confirmed.values()),
            'pending_mapping_rows':sum(r['mapping_owner_ack_required']=='True' for r in rows),
            'original_review_csv_changed':False,'raw_files_changed':False,'new_model_API_calls':0}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['snapshot','confirmation','review-csv']:p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();print(json.dumps(apply_confirmation(a.snapshot,a.confirmation,a.review_csv),indent=2))
