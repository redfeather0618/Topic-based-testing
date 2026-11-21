"""R03 未先向金融服務業申訴 —— 金保法 §24 II 三。"""

from conftest import facts

from foi_screening.params import DEFAULT_PARAMS
from foi_screening.results import Verdict
from foi_screening.rules import r03


def test_未申訴_判定有障礙():
    result = r03.check(facts(has_complained=False), DEFAULT_PARAMS)
    assert result.verdict is Verdict.BLOCKED


def test_已申訴_判定通過():
    result = r03.check(facts(has_complained=True), DEFAULT_PARAMS)
    assert result.verdict is Verdict.CLEAR


def test_未填答_判定資料不足而非有障礙():
    """None 代表使用者沒填，不得當成 False 推進判斷。"""
    result = r03.check(facts(has_complained=None), DEFAULT_PARAMS)
    assert result.verdict is Verdict.INSUFFICIENT


def test_未申訴時給出可執行的補救動作():
    result = r03.check(facts(has_complained=False), DEFAULT_PARAMS)
    assert result.remedy
    assert "申訴" in result.remedy


def test_未申訴屬於可補正的情形():
    """§24 II 但書：可補正者應通知補正，不直接不受理。"""
    result = r03.check(facts(has_complained=False), DEFAULT_PARAMS)
    assert result.correctable is True


def test_資料不足時的補救動作指名欄位():
    result = r03.check(facts(has_complained=None), DEFAULT_PARAMS)
    assert result.remedy
    assert "F07" in result.remedy


def test_帶出條文依據():
    result = r03.check(facts(), DEFAULT_PARAMS)
    assert "金保法§24 II 三" in result.legal_basis
    assert "金保法§13 II" in result.legal_basis


def test_代碼與名稱():
    result = r03.check(facts(), DEFAULT_PARAMS)
    assert result.code == "R03"
    assert result.name == "未先向金融服務業申訴"
