from datetime import date
import pytest
from foi_screening.engine import screen_rule
from foi_screening.facts import RuleFacts, PriorEvaluation, Proceeding, ProceedingKind, ProceedingStatus
from foi_screening.results import Verdict
from foi_screening.rules import r03, r05, r08
from foi_screening.params import DEFAULT_PARAMS


def explicit(**changes):
    values = vars(RuleFacts(application_date=date(2024,4,2), has_complained=True,
        complaint_date=date(2024,1,1), business_replied=True,
        reply_received_date=date(2024,2,5), proceedings=())).copy()
    values.update(complaint_received_date=date(2024,1,1), business_reply_date=date(2024,1,30), center_received_date=None)
    values.update(changes)
    return RuleFacts(**values)


def test_r03_future_complaint_cannot_clear():
    f = RuleFacts(has_complained=True, complaint_date=date(2024,1,20), application_date=date(2024,1,10))
    assert screen_rule('R03', f).verdict is Verdict.INSUFFICIENT
    assert r03.check(f, DEFAULT_PARAMS).verdict is Verdict.INSUFFICIENT


def test_r05_timely_business_reply_later_consumer_receipt():
    result = r05.check(explicit(), DEFAULT_PARAMS)
    assert result.verdict is Verdict.CLEAR
    assert result.computed['start_dates']['§13 II'] == date(2024,2,5)


def test_r05_processing_clock_uses_business_receipt():
    result = r05.check(explicit(complaint_received_date=date(2024,1,10), business_replied=False,
        business_reply_date=None, reply_received_date=None), DEFAULT_PARAMS)
    assert result.computed['start_dates']['§13 II'] == date(2024,2,9)


@pytest.mark.parametrize('code', ['R04','R05'])
def test_legacy_submission_date_does_not_establish_business_receipt(code):
    f = RuleFacts(application_date=date(2024,4,15), has_complained=True,
        complaint_date=date(2024,1,1), business_replied=False, proceedings=())
    assert screen_rule(code,f).verdict is Verdict.INSUFFICIENT


def test_receipt_date_does_not_establish_reply_action_date():
    assert r05.check(explicit(business_reply_date=None), DEFAULT_PARAMS).verdict is Verdict.INSUFFICIENT


def test_r07_withdrawal_is_explicit_not_relabelled_rejected():
    withdrawn = getattr(PriorEvaluation, 'WITHDRAWN', None)
    assert withdrawn is not None
    assert screen_rule('R07', RuleFacts(prior_evaluation=withdrawn)).verdict is Verdict.BLOCKED
    assert withdrawn is not PriorEvaluation.REJECTED


@pytest.mark.parametrize('scope,want', [(None,Verdict.INSUFFICIENT),(False,Verdict.CLEAR),(True,Verdict.BLOCKED)])
def test_r08_requires_current_case_scope(scope,want):
    p = Proceeding(kind=ProceedingKind.SETTLEMENT,status=ProceedingStatus.CONCLUDED,
        date=date(2024,2,1),covers_current_case=scope)
    assert r08.check(RuleFacts(application_date=date(2024,3,1), proceedings=(p,)), DEFAULT_PARAMS).verdict is want


def test_center_receipt_is_an_independent_r05_endpoint():
    f = explicit(application_date=None, center_received_date=date(2024,4,2))
    result = screen_rule('R05', f)
    assert result.verdict is Verdict.CLEAR
    assert f.application_date is None
    assert result.computed['comparison_date'] == date(2024,4,2)
    assert result.computed['comparison_basis'] == 'center_received_date'

@pytest.mark.parametrize('changes', [
    {'complaint_received_date':date(2023,12,31)},
    {'business_reply_date':date(2023,12,31)},
    {'business_reply_date':date(2024,2,6)},
    {'business_reply_date':date(2024,4,3)},
    {'center_received_date':date(2024,4,1)},
])
def test_separate_event_chronology_is_validated(changes):
    assert screen_rule('R05', explicit(**changes)).verdict is Verdict.INSUFFICIENT


def test_unrelated_future_settlement_does_not_block_current_case():
    f = RuleFacts(application_date=date(2024,3,1), proceedings=(
        Proceeding(ProceedingKind.SETTLEMENT, ProceedingStatus.CONCLUDED, date(2024,4,1), False),))
    assert screen_rule('R08', f).verdict is Verdict.CLEAR


def test_r08_unknown_completion_date_at_known_filing_is_insufficient():
    f = RuleFacts(application_date=date(2024,3,1), proceedings=(
        Proceeding(ProceedingKind.SETTLEMENT, ProceedingStatus.CONCLUDED, None, True),))
    assert screen_rule('R08', f).verdict is Verdict.INSUFFICIENT


def test_r03_does_not_depend_on_later_reply():
    f = RuleFacts(has_complained=True, complaint_date=date(2024,1,1),
        application_date=date(2024,1,10), reply_received_date=date(2024,1,20))
    assert screen_rule('R03', f).verdict is Verdict.CLEAR


def test_unrelated_failed_mediation_cannot_extend_current_case_deadline():
    f = explicit(application_date=date(2024,5,1), proceedings=(
        Proceeding(ProceedingKind.MEDIATION_OTHER, ProceedingStatus.FAILED, date(2024,4,1), False),))
    assert screen_rule('R05', f).verdict is Verdict.BLOCKED



def test_268_dates_center_receipt_controls_historical_deadline():
    # Dates from 115-268; complaint receipt is explicitly synthetic for this
    # isolated endpoint regression, not a claim that the PDF establishes it.
    f = RuleFacts(application_date=date(2026,1,5), center_received_date=date(2026,1,16),
        has_complained=True, complaint_received_date=date(2025,11,1),
        business_replied=True, business_reply_date=date(2025,11,13),
        reply_received_date=date(2025,11,13), proceedings=())
    result = screen_rule('R05', f)
    assert result.verdict is Verdict.BLOCKED
    assert result.computed['comparison_date'] == date(2026,1,16)
    assert result.computed['latest_deadline'] == date(2026,1,12)
    assert '中心收文日' in result.reason
    assert f.application_date == date(2026,1,5)


def test_reply_after_submission_before_center_receipt_is_valid_for_r05_only():
    f = explicit(application_date=date(2024,1,20), center_received_date=date(2024,2,10))
    assert screen_rule('R05',f).verdict is Verdict.CLEAR
    assert screen_rule('R04',f).verdict is Verdict.INSUFFICIENT
    assert screen_rule('R03',f).verdict is Verdict.CLEAR


def test_r05_prospective_fallback_explains_endpoint():
    result = screen_rule('R05', explicit())
    assert result.computed['comparison_basis'] == 'application_date_estimate'
    assert '估算' in result.reason



@pytest.mark.parametrize('concluded_on', [None, date(2024,2,1)])
def test_r08_relevant_conclusion_requires_observation_date(concluded_on):
    f = RuleFacts(proceedings=(Proceeding(ProceedingKind.SETTLEMENT,
        ProceedingStatus.CONCLUDED, concluded_on, True),))
    assert screen_rule('R08',f).verdict is Verdict.INSUFFICIENT
    assert screen_rule('R08',RuleFacts(proceedings=())).verdict is Verdict.CLEAR


def test_historical_r05_reply_event_overrides_submission_time_false_status():
    f = explicit(application_date=date(2024,1,20), center_received_date=date(2024,4,3),
        business_replied=False)
    result = screen_rule('R05', f)
    assert result.verdict is Verdict.CLEAR
    assert result.computed['start_dates']['§13 II'] == date(2024,2,5)
    assert f.business_replied is False
    assert screen_rule('R04',f).verdict is Verdict.INSUFFICIENT


def test_historical_r05_complaint_event_overrides_submission_time_false_status():
    f = RuleFacts(application_date=date(2024,1,1), center_received_date=date(2024,5,1),
        has_complained=False, complaint_date=date(2024,1,10),
        complaint_received_date=date(2024,1,10), business_replied=False,
        proceedings=())
    result = screen_rule('R05', f)
    assert result.verdict is Verdict.BLOCKED
    assert result.computed['start_dates']['§13 II'] == date(2024,2,9)
    assert f.has_complained is False
    assert screen_rule('R03',f).verdict is Verdict.INSUFFICIENT


def test_historical_reply_date_without_receipt_cannot_follow_no_reply_branch():
    f = explicit(application_date=date(2024,1,20), center_received_date=date(2024,4,3),
        business_replied=False, reply_received_date=None)
    assert screen_rule('R05', f).verdict is Verdict.INSUFFICIENT


def test_historical_submitted_complaint_without_business_receipt_is_not_no_route():
    f = RuleFacts(application_date=date(2024,1,1), center_received_date=date(2024,5,1),
        has_complained=False, complaint_date=date(2024,1,10),
        business_replied=False, proceedings=())
    assert screen_rule('R05',f).verdict is Verdict.INSUFFICIENT
