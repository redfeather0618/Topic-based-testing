"""R09-1 其他主管機關規定之情形 —— 形式檢查層。

金保法 §24 II 九的內容即評議程序辦法 §15 I 九：
「申請評議事件純屬債務協商、投資表現、信用評等或定價政策之範圍者。」

本層只確認爭議類別落不落在那四類清單內。條文的限定詞「純屬」需讀懂爭議內容，
已整個歸給 R09-2（階段 B），因此 R09-1 永遠不會輸出 BLOCKED。
"""

import pytest
from conftest import facts as base_facts

from foi_screening.facts import ApplicationFacts, DisputeCategory
from foi_screening.params import DEFAULT_PARAMS
from foi_screening.results import Verdict
from foi_screening.rules import r09_1


def facts(category: DisputeCategory | None) -> ApplicationFacts:
    return base_facts(dispute_category=category)


LISTED = [
    DisputeCategory.DEBT_NEGOTIATION,
    DisputeCategory.INVESTMENT_PERFORMANCE,
    DisputeCategory.CREDIT_RATING,
    DisputeCategory.PRICING_POLICY,
]
ALL_ANSWERS = list(DisputeCategory) + [None]


def test_未填爭議類別為資料不足():
    result = r09_1.check(facts(None), DEFAULT_PARAMS)
    assert result.verdict is Verdict.INSUFFICIENT
    assert result.remedy


def test_以上皆非為無此障礙():
    result = r09_1.check(facts(DisputeCategory.NONE_OF_THESE), DEFAULT_PARAMS)
    assert result.verdict is Verdict.CLEAR
    assert result.computed["listed"] is False


@pytest.mark.parametrize("category", LISTED)
def test_落入列舉四類仍為無此障礙且說明提及R09_2(category):
    """本層無權宣告不受理 —— 判 BLOCKED 等於替 R09-2 下結論。"""
    result = r09_1.check(facts(category), DEFAULT_PARAMS)
    assert result.verdict is Verdict.CLEAR
    assert result.computed["listed"] is True
    assert result.computed["category"] == category.value
    assert "R09-2" in result.reason
    assert "純屬" in result.reason


@pytest.mark.parametrize("category", ALL_ANSWERS)
def test_任何填答都不會產生有障礙(category):
    assert r09_1.check(facts(category), DEFAULT_PARAMS).verdict is not Verdict.BLOCKED


@pytest.mark.parametrize("category", ALL_ANSWERS)
def test_一律標示為依使用者自陳(category):
    assert r09_1.check(facts(category), DEFAULT_PARAMS).self_declared is True


@pytest.mark.parametrize("category", ALL_ANSWERS)
def test_一律帶出條文依據(category):
    basis = r09_1.check(facts(category), DEFAULT_PARAMS).legal_basis
    assert "金保法§24 II 九" in basis
    assert "評議程序辦法§15 I 九" in basis
