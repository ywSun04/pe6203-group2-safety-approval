"""Owner-review delivery cannot silently approve pending or mismatched rows."""
import importlib.util
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('supplement_intake',ROOT/'analysis/member5-supplement/intake.py')
intake=importlib.util.module_from_spec(spec);spec.loader.exec_module(intake)
notes_spec=importlib.util.spec_from_file_location('supplement_notes',ROOT/'analysis/member5-supplement/clarify_notes.py')
notes=importlib.util.module_from_spec(notes_spec);notes_spec.loader.exec_module(notes)


@pytest.mark.parametrize('statuses,acknowledged',[
    (['PENDING_OWNER_CONFIRMATION','PENDING_OWNER_CONFIRMATION'],False),
    (['CONFIRMED_BY_OWNER','PENDING_OWNER_CONFIRMATION'],False),
    (['CONFIRMED_BY_OWNER','CONFIRMED_BY_OWNER'],True),
])
def test_mapping_acknowledgement_requires_explicit_complete_confirmation(statuses,acknowledged):
    expected=[{'run_id':'first','hash':'original1'},{'run_id':'second','hash':'original2'}]
    supplied=[dict(row,review_status=status) for row,status in zip(expected,statuses)]
    assert intake.review_table(supplied,expected,['hash'])['owner_confirmation_established'] is acknowledged


def test_confirmed_status_cannot_hide_changed_source_identity():
    with pytest.raises(ValueError,match='identity or source hash'):
        intake.review_table([{'run_id':'first','hash':'changed','review_status':'CONFIRMED_BY_OWNER'}],
                            [{'run_id':'first','hash':'original'}],['hash'])


def test_duplicate_review_row_cannot_hide_missing_uuid():
    supplied=[{'run_id':'first','hash':'original'}]*2
    with pytest.raises(ValueError,match='UUID coverage'):
        intake.review_table(supplied,[{'run_id':'first','hash':'original'},{'run_id':'second','hash':'original'}],['hash'])


def test_zero_completion_tcr_note_does_not_claim_an_authorization_audit():
    group={'n_runs':7,'utility_completed':0,'strict_all_action_TCR':0.0,
           'strict_TCR_note':'M5 explicit executed-action audit'}
    assert notes.clarify(group)['strict_TCR_note']==notes.ZERO_NOTE


def test_positive_utility_does_not_gain_a_safety_label_from_note_correction():
    group={'n_runs':3,'utility_completed':2,'strict_all_action_TCR':None,
           'strict_TCR_note':'Complete authorization audit unavailable'}
    assert notes.clarify(group)['strict_TCR_note']=='Complete authorization audit unavailable'
    assert group['strict_all_action_TCR'] is None
