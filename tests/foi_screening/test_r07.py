"""R07 曾依本法申請評議而不成立 —— 金保法 §24 II 七。"""

import pytest
from conftest import facts as base_facts

from foi_screening.facts import ApplicationFacts, PriorEvaluation
from foi_screening.params import DEFAULT_PARAMS
from foi_screening.results import Verdict
from foi_screening.rules import r07


def facts(prior: PriorEvaluation | None) -> ApplicationFacts:
    return base_facts(prior_evaluation=prior)


def test_曾評議不成立_判定有障礙():
    result = r07.check(facts(PriorEvaluation.REJECTED), DEFAULT_PARAMS)
    assert result.verdict is Verdict.BLOCKED


@pytest.mark.parametrize(
    "prior",
    [PriorEvaluation.NONE, PriorEvaluation.PENDING, PriorEvaluation.ACCEPTED],
)
def test_其餘情形皆不觸發本款(prior):
    """§24 II 七只針對「評議而不成立」。曾申請但成立或尚無結果，都不是本款情形。"""
    result = r07.check(facts(prior), DEFAULT_PARAMS)
    assert result.verdict is Verdict.CLEAR


def test_未填答_判定資料不足():
    result = r07.check(facts(None), DEFAULT_PARAMS)
    assert result.verdict is Verdict.INSUFFICIENT
    assert "F11" in result.remedy


def test_不可補正():
    """曾評議不成立是既成事實，無從補正。"""
    result = r07.check(facts(PriorEvaluation.REJECTED), DEFAULT_PARAMS)
    assert result.correctable is False


def test_標記為使用者自陳且無法查證():
    """大綱 §5.1：R07/R08 依使用者自陳，輸出應標為「依你的填答」而非「經查證」。"""
    result = r07.check(facts(PriorEvaluation.REJECTED), DEFAULT_PARAMS)
    assert result.self_declared is True


def test_帶出條文依據():
    result = r07.check(facts(PriorEvaluation.NONE), DEFAULT_PARAMS)
    assert "金保法§24 II 七" in result.legal_basis
    assert result.code == "R07"
