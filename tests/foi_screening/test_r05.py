"""R05 申請已逾法定期限 —— 金保法 §24 II 五。

兩條起算路徑：

  路徑 A（§13 II）業者於三十日內回覆 → 自收受處理結果之日起六十日
                  業者未於三十日內處理 → 自期限屆滿之日起六十日
  路徑 B（§23 V）依其他法律調處或調解不成立 → 自不成立之日起六十日

只要有任一條路徑仍在期限內，就不構成本款（取較寬的期限）。
"""

from datetime import date

from conftest import facts as base_facts

from foi_screening.facts import (
    ApplicationFacts,
    Proceeding,
    ProceedingKind,
    ProceedingStatus,
)
from foi_screening.params import DEFAULT_PARAMS
from foi_screening.results import Verdict
from foi_screening.rules import r05

COMPLAINT = date(2024, 1, 1)
DEADLINE_30 = date(2024, 1, 31)  # 申訴日 + 30 日（民法§120 始日不算入）


def facts(**overrides) -> ApplicationFacts:
    """本檔的基準案：業者尚未回覆，故起算日為三十日期限屆滿之日。"""
    return base_facts(
        **{
            "complaint_date": COMPLAINT,
            "complaint_received_date": COMPLAINT,
            "business_reply_date": None,
            "business_replied": False,
            "reply_received_date": None,
            **overrides,
        }
    )


def replied(reply_date: date, application_date: date) -> ApplicationFacts:
    return facts(
        business_replied=True,
        reply_received_date=reply_date,
        business_reply_date=reply_date,
        application_date=application_date,
    )


# —— 路徑 A：業者於三十日內回覆，自收受處理結果之日起算 ——


def test_業者期限內回覆_收受日起第六十日提出_未逾期():
    # 回覆 2024-01-20（在 01-31 屆滿前）→ 期限 2024-03-20
    assert r05.check(replied(date(2024, 1, 20), date(2024, 3, 20)), DEFAULT_PARAMS).verdict is Verdict.CLEAR


def test_業者期限內回覆_收受日起第六十一日提出_逾期():
    assert r05.check(replied(date(2024, 1, 20), date(2024, 3, 21)), DEFAULT_PARAMS).verdict is Verdict.BLOCKED


def test_業者期限內回覆時的起算日與期限():
    result = r05.check(replied(date(2024, 1, 20), date(2024, 3, 1)), DEFAULT_PARAMS)
    assert result.computed["deadlines"]["§13 II"] == date(2024, 3, 20)
    assert result.computed["start_dates"]["§13 II"] == date(2024, 1, 20)


# —— 路徑 A：業者未於三十日內處理，自期限屆滿之日起算 ——


def test_業者未回覆_屆滿日起第六十日提出_未逾期():
    # 起算 2024-01-31 → 期限 2024-03-31
    assert r05.check(facts(application_date=date(2024, 3, 31)), DEFAULT_PARAMS).verdict is Verdict.CLEAR


def test_業者未回覆_屆滿日起第六十一日提出_逾期():
    assert r05.check(facts(application_date=date(2024, 4, 1)), DEFAULT_PARAMS).verdict is Verdict.BLOCKED


def test_業者未回覆時以三十日屆滿日為起算():
    result = r05.check(facts(application_date=date(2024, 3, 1)), DEFAULT_PARAMS)
    assert result.computed["start_dates"]["§13 II"] == DEADLINE_30


# —— 路徑 A：業者逾三十日之後才回覆 ——


def test_業者逾期後才回覆_起算仍為三十日屆滿日():
    """已確認之認定：期限屆滿即起算，業者事後回覆不重新起算。

    依評議中心實際案例確認（2026-09-14），不再視為有爭議的認定。

    業者 2024-02-15 才回覆（申訴後第 45 日）。
    起算日仍為屆滿日 2024-01-31 → 期限 2024-03-31，
    2024-04-01 提出已逾期。
    """
    late = replied(date(2024, 2, 15), date(2024, 4, 1))
    result = r05.check(late, DEFAULT_PARAMS)
    assert result.computed["start_dates"]["§13 II"] == DEADLINE_30
    assert result.verdict is Verdict.BLOCKED


def test_業者回覆日再晚都不影響起算日():
    """起算日恆為屆滿日，與回覆日距離多遠無關。"""
    for reply_on in (date(2024, 2, 1), date(2024, 6, 1), date(2025, 1, 1)):
        result = r05.check(replied(reply_on, date(2024, 3, 1)), DEFAULT_PARAMS)
        assert result.computed["start_dates"]["§13 II"] == DEADLINE_30


# —— 期間計算的邊界 ——


def test_跨閏年_二月二十九日被計入():
    """申訴 2024-01-15 → 屆滿 2024-02-14 → 六十日期限 2024-04-14。"""
    result = r05.check(
        facts(complaint_date=date(2024, 1, 15), complaint_received_date=date(2024, 1, 15), application_date=date(2024, 4, 14)),
        DEFAULT_PARAMS,
    )
    assert result.computed["deadlines"]["§13 II"] == date(2024, 4, 14)
    assert result.verdict is Verdict.CLEAR


# —— 路徑 B：§23 V 調處／調解不成立 ——


def mediation_failed(kind: ProceedingKind, on: date) -> Proceeding:
    return Proceeding(kind=kind, status=ProceedingStatus.FAILED, date=on)


def test_調解不成立_自不成立日起第六十日提出_未逾期():
    # 不成立 2024-03-01 → 期限 2024-04-30
    result = r05.check(
        facts(
            has_complained=False,
            complaint_date=None,
            application_date=date(2024, 4, 30),
            proceedings=(mediation_failed(ProceedingKind.MEDIATION_OTHER, date(2024, 3, 1)),),
        ),
        DEFAULT_PARAMS,
    )
    assert result.verdict is Verdict.CLEAR
    assert result.computed["deadlines"]["§23 V"] == date(2024, 4, 30)


def test_調解不成立_自不成立日起第六十一日提出_逾期():
    result = r05.check(
        facts(
            has_complained=False,
            complaint_date=None,
            application_date=date(2024, 5, 1),
            proceedings=(mediation_failed(ProceedingKind.MEDIATION_OTHER, date(2024, 3, 1)),),
        ),
        DEFAULT_PARAMS,
    )
    assert result.verdict is Verdict.BLOCKED


def test_調處不成立同樣適用():
    result = r05.check(
        facts(
            has_complained=False,
            complaint_date=None,
            application_date=date(2024, 4, 30),
            proceedings=(mediation_failed(ProceedingKind.MEDIATION_FOI, date(2024, 3, 1)),),
        ),
        DEFAULT_PARAMS,
    )
    assert result.verdict is Verdict.CLEAR


def test_和解不成立不適用第二十三條第五項():
    """§23 V 只給「調處或調解不成立」新的視窗，不含和解、仲裁。"""
    result = r05.check(
        facts(
            has_complained=False,
            complaint_date=None,
            application_date=date(2024, 4, 30),
            proceedings=(mediation_failed(ProceedingKind.SETTLEMENT, date(2024, 3, 1)),),
        ),
        DEFAULT_PARAMS,
    )
    assert "§23 V" not in result.computed["deadlines"]


def test_調解成立不開啟新視窗():
    """成立者屬 R08，不是 §23 V 的情形。"""
    result = r05.check(
        facts(
            has_complained=False,
            complaint_date=None,
            application_date=date(2024, 4, 30),
            proceedings=(
                Proceeding(ProceedingKind.MEDIATION_OTHER, ProceedingStatus.CONCLUDED, date(2024, 3, 1)),
            ),
        ),
        DEFAULT_PARAMS,
    )
    assert "§23 V" not in result.computed["deadlines"]


# —— 多路徑取較寬 ——


def test_雙路徑並存時取較晚的期限():
    """§13 II 期限 2024-03-31 已過，但 §23 V 期限 2024-04-30 未過 → 未逾期。"""
    result = r05.check(
        facts(
            application_date=date(2024, 4, 20),
            proceedings=(mediation_failed(ProceedingKind.MEDIATION_OTHER, date(2024, 3, 1)),),
        ),
        DEFAULT_PARAMS,
    )
    assert result.computed["deadlines"] == {"§13 II": date(2024, 3, 31), "§23 V": date(2024, 4, 30)}
    assert result.verdict is Verdict.CLEAR


def test_雙路徑皆已逾期才判定有障礙():
    result = r05.check(
        facts(
            application_date=date(2024, 5, 1),
            proceedings=(mediation_failed(ProceedingKind.MEDIATION_OTHER, date(2024, 3, 1)),),
        ),
        DEFAULT_PARAMS,
    )
    assert result.verdict is Verdict.BLOCKED


def test_多筆調解不成立取最晚者():
    result = r05.check(
        facts(
            has_complained=False,
            complaint_date=None,
            application_date=date(2024, 4, 30),
            proceedings=(
                mediation_failed(ProceedingKind.MEDIATION_OTHER, date(2024, 1, 1)),
                mediation_failed(ProceedingKind.MEDIATION_FOI, date(2024, 3, 1)),
            ),
        ),
        DEFAULT_PARAMS,
    )
    assert result.computed["deadlines"]["§23 V"] == date(2024, 4, 30)
    assert result.verdict is Verdict.CLEAR


# —— 前提不成立與資料不足 ——


def test_沒有任何起算路徑_本款不成立():
    """未申訴且無調解不成立 → 六十日期間根本尚未起算，不可能逾期。障礙在 R03。"""
    result = r05.check(facts(has_complained=False, complaint_date=None), DEFAULT_PARAMS)
    assert result.verdict is Verdict.CLEAR
    assert "R03" in result.reason


def test_已申訴但未填申訴日_資料不足():
    result = r05.check(facts(complaint_received_date=None), DEFAULT_PARAMS)
    assert result.verdict is Verdict.INSUFFICIENT
    assert "F08" in result.remedy


def test_業者已回覆但未填收受日_資料不足():
    result = r05.check(
        facts(business_replied=True, business_reply_date=date(2024,1,20), reply_received_date=None), DEFAULT_PARAMS
    )
    assert result.verdict is Verdict.INSUFFICIENT
    assert "F09" in result.remedy


def test_調解不成立但未填日期_資料不足():
    result = r05.check(
        facts(
            has_complained=False,
            complaint_date=None,
            proceedings=(Proceeding(ProceedingKind.MEDIATION_OTHER, ProceedingStatus.FAILED, None),),
        ),
        DEFAULT_PARAMS,
    )
    assert result.verdict is Verdict.INSUFFICIENT
    assert "F12" in result.remedy


# —— 性質與出處 ——


def test_逾期不可補正():
    result = r05.check(facts(application_date=date(2024, 4, 1)), DEFAULT_PARAMS)
    assert result.correctable is False


def test_逾期時說明期限是哪一天():
    result = r05.check(facts(application_date=date(2024, 4, 1)), DEFAULT_PARAMS)
    assert "2024-03-31" in result.reason


def test_帶出條文依據():
    result = r05.check(facts(), DEFAULT_PARAMS)
    assert "金保法§24 II 五" in result.legal_basis
    assert "金保法§13 II" in result.legal_basis
    assert "民法§120" in result.legal_basis
    assert result.code == "R05"
    assert result.name == "申請已逾法定期限"
