"""R04 申訴處理中尚未逾三十日 —— 金保法 §24 II 四。

「向金融服務業提出申訴後，金融服務業**處理申訴中**尚未逾三十日。」

「處理申訴中」是本款的核心：業者一旦回覆，申訴就不在處理中，
本款即不成立，申請人不必等滿三十日。
"""

from datetime import date

from conftest import facts as base_facts

from foi_screening.facts import ApplicationFacts
from foi_screening.params import DEFAULT_PARAMS
from foi_screening.results import Verdict
from foi_screening.rules import r04

COMPLAINT = date(2024, 1, 1)
# 民法§120 始日不算入 → 三十日期限屆滿日為 2024-01-31
DEADLINE_30 = date(2024, 1, 31)


def facts(**overrides) -> ApplicationFacts:
    """本檔的基準案：業者尚未回覆，2024-02-01 提出申請（已逾三十日）。"""
    return base_facts(
        **{
            "application_date": date(2024, 2, 1),
            "complaint_date": COMPLAINT,
            "complaint_received_date": COMPLAINT,
            "business_reply_date": None,
            "business_replied": False,
            "reply_received_date": None,
            **overrides,
        }
    )


# —— 業者尚未回覆：以三十日期限判斷 ——


def test_業者未回覆_申訴後第二十九日提出_有障礙():
    result = r04.check(facts(application_date=date(2024, 1, 30)), DEFAULT_PARAMS)
    assert result.verdict is Verdict.BLOCKED


def test_業者未回覆_申訴後第三十日提出_仍有障礙():
    """民法§121：期間以末日之終止為終止。屆滿日當天仍屬「尚未逾三十日」。"""
    result = r04.check(facts(application_date=DEADLINE_30), DEFAULT_PARAMS)
    assert result.verdict is Verdict.BLOCKED


def test_業者未回覆_申訴後第三十一日提出_通過():
    result = r04.check(facts(application_date=date(2024, 2, 1)), DEFAULT_PARAMS)
    assert result.verdict is Verdict.CLEAR


def test_有障礙時告知還需等待幾天():
    result = r04.check(facts(application_date=date(2024, 1, 30)), DEFAULT_PARAMS)
    assert result.computed["days_to_wait"] == 1
    assert result.computed["deadline"] == DEADLINE_30


def test_有障礙時屬可補正情形():
    result = r04.check(facts(application_date=date(2024, 1, 30)), DEFAULT_PARAMS)
    assert result.correctable is True


# —— 業者已回覆：本款恆不成立 ——


def test_業者第十日即回覆_第十一日提出_通過():
    """關鍵案例：業者已回覆＝不在「處理申訴中」，不必等滿三十日。"""
    result = r04.check(
        facts(
            application_date=date(2024, 1, 11),
            business_replied=True,
            reply_received_date=date(2024, 1, 10),
        ),
        DEFAULT_PARAMS,
    )
    assert result.verdict is Verdict.CLEAR


def test_業者回覆後隔日即提出_仍通過():
    result = r04.check(
        facts(
            application_date=date(2024, 1, 3),
            business_replied=True,
            reply_received_date=date(2024, 1, 2),
        ),
        DEFAULT_PARAMS,
    )
    assert result.verdict is Verdict.CLEAR


# —— 前提不成立與資料不足 ——


def test_尚未申訴_本款不適用():
    """未申訴者由 R03 處理；本款以「向金融服務業提出申訴後」為前提。"""
    result = r04.check(facts(has_complained=False), DEFAULT_PARAMS)
    assert result.verdict is Verdict.CLEAR
    assert "R03" in result.reason


def test_申訴日未填_資料不足():
    result = r04.check(facts(complaint_received_date=None), DEFAULT_PARAMS)
    assert result.verdict is Verdict.INSUFFICIENT
    assert "F08" in result.remedy


def test_業者是否回覆未填_資料不足():
    result = r04.check(facts(business_replied=None), DEFAULT_PARAMS)
    assert result.verdict is Verdict.INSUFFICIENT
    assert "F09" in result.remedy


def test_是否申訴未填_資料不足():
    result = r04.check(facts(has_complained=None), DEFAULT_PARAMS)
    assert result.verdict is Verdict.INSUFFICIENT


# —— 條文出處 ——


def test_帶出條文依據():
    result = r04.check(facts(), DEFAULT_PARAMS)
    assert "金保法§24 II 四" in result.legal_basis
    assert "金保法§13 II" in result.legal_basis
    assert "民法§120" in result.legal_basis
    assert result.code == "R04"
    assert result.name == "申訴處理尚未逾三十日"
