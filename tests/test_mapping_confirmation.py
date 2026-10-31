"""An explicit confirmation stays bound to the exact reviewed mapping."""
import copy
import importlib.util
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('explicit_mapping_confirmation',ROOT/'analysis/member5-supplement/confirm_mapping.py')
confirmation=importlib.util.module_from_spec(spec);spec.loader.exec_module(confirmation)


def example():
    raw=b'run_id,review_status\na,PENDING_OWNER_CONFIRMATION\nb,PENDING_OWNER_CONFIRMATION\n'
    declaration={'status':confirmation.STATUS,'scope':sorted(confirmation.SCOPE),
        'source_reference':'Explicit user message after the supplied review table',
        'review_csv_sha256':confirmation.sha(raw),'confirmed_run_ids':['a','b'],
        'confirmed_row_count':2,'confirmed_uuid_set_sha256':confirmation.sha(b'a\nb\n')}
    return declaration,raw


def test_later_explicit_confirmation_does_not_rewrite_original_pending_csv():
    declaration,raw=example();before=bytes(raw)
    accepted=confirmation.validate_confirmation(declaration,raw)
    assert set(accepted)=={'a','b'}
    assert all(row['review_status']=='PENDING_OWNER_CONFIRMATION' for row in accepted.values())
    assert raw==before


@pytest.mark.parametrize('defect',['missing_id','duplicate_id','missing_scope','wrong_status','wrong_set_hash'])
def test_incomplete_or_unbound_confirmation_is_rejected(defect):
    declaration,raw=example()
    if defect=='missing_id':declaration['confirmed_run_ids']=['a']
    elif defect=='duplicate_id':declaration['confirmed_run_ids']=['a','a']
    elif defect=='missing_scope':declaration['scope']=['repetition_mapping']
    elif defect=='wrong_status':declaration['status']='PENDING_OWNER_CONFIRMATION'
    elif defect=='wrong_set_hash':declaration['confirmed_uuid_set_sha256']='0'*64
    with pytest.raises(ValueError):confirmation.validate_confirmation(declaration,raw)


def test_modified_source_review_bytes_are_rejected():
    declaration,raw=example()
    with pytest.raises(ValueError,match='CSV bytes'):
        confirmation.validate_confirmation(declaration,raw+b'c,PENDING_OWNER_CONFIRMATION\n')


def test_confirmation_cannot_cover_a_different_attempt_role():
    row={'run_id':'a','task_id':'task','policy':'full-approve','k':'1','condition':'none',
         'raw_repetition':'0','mapped_repetition':'1','role':'retry_formal',
         'primary_run_id':'first','raw_manifest_sha256':'source'}
    changed=copy.deepcopy(row);changed['role']='primary_formal'
    with pytest.raises(ValueError,match='role'):confirmation.bind_row(changed,row)


@pytest.mark.parametrize('pending_ids',[{'a'},{'a','b','c'}])
def test_closure_cannot_clear_an_incomplete_or_extra_pending_scope(pending_ids):
    rows=[{'run_id':rid,'mapping_owner_ack_required':'True'} for rid in pending_ids]
    with pytest.raises(ValueError,match='scope'):confirmation.validate_pending_scope(rows,{'a','b'})


def test_idempotent_closure_requires_the_prior_confirmation_status():
    rows=[{'run_id':rid,'mapping_owner_ack_required':'False','mapping_confirmation_status':confirmation.STATUS} for rid in ['a','b']]
    confirmation.validate_pending_scope(rows,{'a','b'})
    rows[1]['mapping_confirmation_status']='unrecorded'
    with pytest.raises(ValueError,match='prior closure'):confirmation.validate_pending_scope(rows,{'a','b'})
