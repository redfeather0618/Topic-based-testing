"""Missing facts must not produce a definite deadline or a fabricated date."""
from datetime import date

import pytest

from conftest import complete_facts
from foi_screening import screen
from foi_screening.engine import screen_rule
from foi_screening.facts import RuleFacts, PriorEvaluation, Proceeding, ProceedingKind, ProceedingStatus
from foi_screening.params import DEFAULT_PARAMS
from foi_screening.results import Verdict
from foi_screening.rules import r05


@pytest.mark.parametrize('changes', [
    {'has_complained': None, 'complaint_date': None},
    {'business_replied': None, 'reply_received_date': None},
    {'proceedings': None},
])
def test_unknown_deadline_routes_cannot_be_assumed_absent(changes):
    facts = complete_facts(application_date=date(2024, 5, 1), **changes)
    assert r05.check(facts, DEFAULT_PARAMS).verdict is Verdict.INSUFFICIENT


def test_known_open_route_can_clear_despite_unknown_other_route():
    facts = complete_facts(application_date=date(2024, 3, 1), proceedings=None)
    assert r05.check(facts, DEFAULT_PARAMS).verdict is Verdict.CLEAR


def test_known_mediation_route_can_clear_with_unknown_complaint():
    facts = complete_facts(has_complained=None, application_date=date(2024, 3, 1),
        proceedings=(Proceeding(ProceedingKind.MEDIATION_OTHER, ProceedingStatus.FAILED, date(2024, 2, 1)),))
    assert r05.check(facts, DEFAULT_PARAMS).verdict is Verdict.CLEAR


@pytest.mark.parametrize('application,want', [
    (date(2024, 3, 1), Verdict.CLEAR),
    (date(2024, 5, 1), Verdict.INSUFFICIENT),
])
def test_one_undated_mediation_does_not_discard_another_known_route(application, want):
    facts = RuleFacts(application_date=application, has_complained=False,
        proceedings=(
            Proceeding(ProceedingKind.MEDIATION_OTHER, ProceedingStatus.FAILED, date(2024, 2, 1)),
            Proceeding(ProceedingKind.MEDIATION_OTHER, ProceedingStatus.FAILED, None),
        ))
    assert screen_rule('R05', facts).verdict is want


def test_r08_cannot_use_a_future_completed_proceeding():
    facts = RuleFacts(application_date=date(2024, 3, 1), proceedings=(
        Proceeding(ProceedingKind.SETTLEMENT, ProceedingStatus.CONCLUDED, date(2024, 4, 1)),))
    result = screen_rule('R08', facts)
    assert result.verdict is Verdict.INSUFFICIENT
    assert result.computed['input_errors']


def test_non_date_rule_needs_no_fake_application_date():
    facts = RuleFacts(has_complained=False)
    assert screen_rule('R03', facts).verdict is Verdict.BLOCKED
    assert facts.application_date is None
    assert screen_rule('R07', RuleFacts(prior_evaluation=PriorEvaluation.REJECTED)).verdict is Verdict.BLOCKED


def test_date_rule_without_application_date_is_insufficient():
    facts = RuleFacts(has_complained=True, complaint_date=date(2024, 1, 1), business_replied=False)
    assert screen_rule('R04', facts).verdict is Verdict.INSUFFICIENT
    assert screen_rule('R05', facts).verdict is Verdict.INSUFFICIENT


@pytest.mark.parametrize('changes', [
    {'complaint_date': date(2024, 2, 1), 'reply_received_date': date(2024, 1, 20)},
    {'complaint_date': date(2024, 4, 1)},
])
def test_inconsistent_dates_do_not_reach_deadline_comparison(changes):
    result = screen_rule('R05', complete_facts(**changes))
    assert result.verdict is Verdict.INSUFFICIENT
    assert result.computed['input_errors']


def test_date_rule_reuses_sensitivity_and_matches_full_engine():
    facts = complete_facts(application_date=date(2024, 4, 1), business_replied=False, reply_received_date=None)
    result = screen_rule('R05', facts)
    assert result.verdict is Verdict.DISPUTED
    assert result == screen(facts).by_code('R05')


@pytest.mark.parametrize('code', ['R01', 'R01-1', 'R02', 'R06', 'R09', 'R09-1'])
def test_partial_entrypoint_never_activates_deferred_rules(code):
    with pytest.raises(ValueError):
        screen_rule(code, RuleFacts())
