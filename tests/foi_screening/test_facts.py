"""新增欄位的型別與預設值。

兩個新欄位必須有 None 預設值 —— 既有測試檔都直接建構 ApplicationFacts，
若無預設值會全部壞掉；且 None 本來就代表「使用者沒填」，語意正確。
"""

# facts() 不傳新欄位，正是既有測試原本的建構方式
from conftest import COMPLETE_READINESS, facts

from foi_screening.facts import (
    LISTED_CATEGORIES,
    ApplicationReadiness,
    DisputeCategory,
    SubmissionMethod,
)


def test_新欄位預設為未填():
    minimal = facts()
    assert minimal.readiness is None
    assert minimal.dispute_category is None


def test_列舉四類不含以上皆非():
    assert DisputeCategory.NONE_OF_THESE not in LISTED_CATEGORIES
    assert LISTED_CATEGORIES == {
        DisputeCategory.DEBT_NEGOTIATION,
        DisputeCategory.INVESTMENT_PERFORMANCE,
        DisputeCategory.CREDIT_RATING,
        DisputeCategory.PRICING_POLICY,
    }


def test_送件方式有紙本與線上兩種():
    assert {m.name for m in SubmissionMethod} == {"PAPER", "ONLINE"}


def test_齊備情形可全部留空():
    """每個欄位都必須接受 None —— 使用者還沒開始準備時就是這個狀態。

    用 COMPLETE_READINESS 的鍵來建構：若日後新增了沒有預設值的欄位而
    漏了同步共用建構器，這裡會直接 TypeError，不會靜默漏測。
    """
    empty = ApplicationReadiness(**dict.fromkeys(COMPLETE_READINESS))
    assert empty.submission_method is None
    assert empty.has_application_form is None
