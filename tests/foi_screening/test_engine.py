"""引擎整合 —— 十一碼恆存、覆蓋範圍揭露、法律認定爭議的偵測。

大綱 §4.3、§5.2、§7：階段 A 只覆蓋 11 碼中的 7 碼，**絕不能輸出「你沒有問題」**。
這裡用型別與斷言把它釘死，而不是靠寫文案時自律。
"""

from datetime import date

import pytest

# complete_facts()：一份完全乾淨、七碼全通過的申請（見 tests/conftest.py）
from conftest import complete_facts as facts

from foi_screening import screen
from foi_screening.engine import ALL_CODES, COVERED, NOT_COVERED_CODES
from foi_screening.facts import (
    PriorEvaluation,
    Proceeding,
    ProceedingKind,
    ProceedingStatus,
)
from foi_screening.params import DEFAULT_PARAMS
from foi_screening.results import Verdict


# —— 十一碼恆存 ——


def test_永遠回傳十一碼且依序排列():
    report = screen(facts())
    assert tuple(r.code for r in report.results) == ALL_CODES
    assert len(report.results) == 11


def test_R01拆成形式檢查層與理解判斷層():
    """R01 依檢查層次拆成兩碼；拆分是本專案的分析，兩碼同屬 §24 II 一。"""
    report = screen(facts())
    codes = [r.code for r in report.results]
    assert "R01" not in codes
    assert codes[:2] == ["R01-1", "R01-2"]
    for code in ("R01-1", "R01-2"):
        assert "金保法§24 II 一" in report.by_code(code).legal_basis


def test_R09拆成形式檢查層與理解判斷層():
    """R09 的內容是評議程序辦法 §15 I 九的四類具名情形，不是開放條款。"""
    report = screen(facts())
    codes = [r.code for r in report.results]
    assert "R09" not in codes
    assert codes[-2:] == ["R09-1", "R09-2"]
    for code in ("R09-1", "R09-2"):
        result = report.by_code(code)
        assert "金保法§24 II 九" in result.legal_basis
        assert "評議程序辦法§15 I 九" in result.legal_basis


def test_R09不再宣稱定義開放():
    """回歸測試：辦法 §15 I 九列舉四類，說「定義開放」是錯誤資訊。"""
    report = screen(facts())
    for code in ("R09-1", "R09-2"):
        assert "定義開放" not in report.by_code(code).reason


def test_R09形式檢查層未填類別時列出四類具名情形():
    """未填類別時，文案要把辦法 §15 I 九的四類列出來供使用者對照。"""
    result = screen(facts(dispute_category=None)).by_code("R09-1")
    assert result.verdict is Verdict.INSUFFICIENT
    for category in ("債務協商", "投資表現", "信用評等", "定價政策"):
        assert category in result.remedy


def test_R09兩碼均不可補正():
    """事件性質不屬受理範圍，與 R01 的程式瑕疵不同，無從補正。"""
    report = screen(facts())
    for code in ("R09-1", "R09-2"):
        assert not report.by_code(code).correctable


@pytest.mark.parametrize("code", NOT_COVERED_CODES)
def test_未覆蓋的四碼恆為不檢查(code):
    """四個未覆蓋碼是「引擎明示不檢查」，不是「忘了實作而缺席」。"""
    report = screen(facts(has_complained=False, prior_evaluation=PriorEvaluation.REJECTED))
    result = report.by_code(code)
    assert result.verdict is Verdict.NOT_COVERED
    assert result.legal_basis  # 仍帶條文出處，供條文對照審查


def test_R01理解判斷層標示為可補正且補救文案具體():
    """§24 II 但書：申請不合程式可以補正。

    不檢查不等於沒話可說 —— R01-2 即使本工具不判斷，也應告訴使用者
    「這是可以補正的」，而不是給「請自行評估」的通用文案。
    （R01-1 已是實規則，其可補正性見 tests/test_r01_1.py。）
    """
    result = screen(facts()).by_code("R01-2")
    assert result.correctable
    assert "補正" in result.remedy
    assert "請自行評估" not in result.remedy


def test_R01兩碼引用評議程序辦法():
    """程式上的要求來自辦法 §13（應載明事項）與 §14（補正），不只 §24 II 一。

    本測試橫跨 R01-1（已實作的規則）與 R01-2（尚未實作的樁）：
    兩碼共享法條依據不代表同性質，R01-2 仍是 NOT_COVERED 的佔位。
    """
    report = screen(facts())
    assert "評議程序辦法§13" in report.by_code("R01-1").legal_basis
    assert "評議程序辦法§14" in report.by_code("R01-1").legal_basis
    assert "評議程序辦法§13" in report.by_code("R01-2").legal_basis


def test_其餘未覆蓋碼維持通用補救文案():
    """R02/R06 沒有可對照的具名清單，也無可補正依據，維持通用文案才誠實。"""
    report = screen(facts())
    for code in ("R02", "R06"):
        result = report.by_code(code)
        assert not result.correctable
        assert "請自行評估" in result.remedy


def test_未覆蓋的四碼也說明為何不檢查():
    result = screen(facts()).by_code("R09-2")
    assert result.reason
    assert "本工具" in result.reason


def test_已實作的碼不得同時列為不檢查():
    """本次同時改動 COVERED 與 NOT_COVERED_CODES，這是最容易漏掉一邊的地方。"""
    assert set(COVERED) & set(NOT_COVERED_CODES) == set()
    assert set(COVERED) | set(NOT_COVERED_CODES) == set(ALL_CODES)


def test_階段A覆蓋七碼():
    assert set(COVERED) == {"R01-1", "R03", "R04", "R05", "R07", "R08", "R09-1"}


# —— 覆蓋範圍的揭露 ——


def test_全部通過時摘要仍不得宣告沒問題():
    report = screen(facts())
    assert all(
        r.verdict is Verdict.CLEAR for r in report.results if r.code not in NOT_COVERED_CODES
    )
    for forbidden in ("沒問題", "可以送件", "符合資格", "會被受理", "沒有問題"):
        assert forbidden not in report.summary_text


def test_摘要必須列出四項未檢查的事由():
    report = screen(facts())
    for code in NOT_COVERED_CODES:
        assert code in report.summary_text
    assert "當事人不適格" in report.summary_text


def test_摘要必須揭露不構成法律意見():
    assert "法律意見" in screen(facts()).summary_text


def test_摘要的通過與障礙數量正確():
    report = screen(facts(has_complained=False))
    # 未申訴：R03 有障礙；R04/R05 不適用而通過；R01-1/R07/R08/R09-1 通過
    assert len(report.blocked) == 1
    assert report.blocked[0].code == "R03"
    assert "通過 6 項" in report.summary_text
    assert "有明確障礙 1 項" in report.summary_text


def test_資料不足會被單獨計數():
    report = screen(facts(prior_evaluation=None))
    assert [r.code for r in report.needs_input] == ["R07"]
    assert "資料不足 1 項" in report.summary_text


def test_未填新欄位時兩條形式檢查層均為資料不足():
    """既有呼叫端不傳 readiness／dispute_category 時，不得靜默得到假 CLEAR。"""
    report = screen(facts(readiness=None, dispute_category=None))
    assert {r.code for r in report.needs_input} == {"R01-1", "R09-1"}
    assert "資料不足 2 項" in report.summary_text


# —— 法律認定有爭議 → DISPUTED ——


def test_末日為休息日造成結論相反時降級為有爭議():
    """申訴 2024-04-01、業者未回覆 → 期限 2024-06-30（星期日）。

    不順延則 2024-07-01 提出已逾期；依民法 §122 順延則末日為 07-01，未逾期。
    兩種認定都站得住腳，引擎必須誠實回報爭議，不得單方面宣告逾期。
    """
    report = screen(
        facts(
            complaint_date=date(2024, 4, 1),
            complaint_received_date=date(2024, 4, 1),
            business_replied=False,
            reply_received_date=None,
            business_reply_date=None,
            application_date=date(2024, 7, 1),
        )
    )
    assert report.by_code("R05").verdict is Verdict.DISPUTED


def test_有爭議時說明爭議何在():
    report = screen(
        facts(
            complaint_date=date(2024, 4, 1),
            complaint_received_date=date(2024, 4, 1),
            business_replied=False,
            reply_received_date=None,
            business_reply_date=None,
            application_date=date(2024, 7, 1),
        )
    )
    result = report.by_code("R05")
    assert "認定" in result.reason
    assert result.remedy


def test_業者逾期後才回覆_不再視為爭議():
    """回歸測試：這組日期原本會降級為 DISPUTED。

    「屆滿即起算，事後回覆不重新起算」已依評議中心實際案例確認（2026-09-14），
    不再是敏感度分析的替代認定，因此本案應直接判為逾期。

    送件日刻意取 2024-04-05 而非期限次日 2024-04-01：期限末日 2024-03-31
    是星期日，04-01 會另外踩中 holiday_rollover 而仍降級為 DISPUTED，
    測不出本次改動。04-05 在兩種順延認定下都已逾期。
    """
    report = screen(
        facts(
            complaint_date=date(2024, 1, 1),
            complaint_received_date=date(2024, 1, 1),
            business_replied=True,
            reply_received_date=date(2024, 2, 15),
            business_reply_date=date(2024, 2, 15),
            application_date=date(2024, 4, 5),
        )
    )
    result = report.by_code("R05")
    assert result.verdict is Verdict.BLOCKED
    assert "alternatives" not in result.computed


def test_末日為週六造成結論相反時同樣降級為有爭議():
    """回歸測試：休息日只認星期日時，這組日期會被直接判 BLOCKED。

    申訴 2024-01-07、業者未回覆 → 三十日屆滿 2024-02-06
    → 六十日末日 2024-04-06（星期六）。2024-04-08 送件：
    不順延已逾期，依民法 §122 順延至 04-08（星期一）則未逾期。
    加入星期六前，兩種認定算出同一天，敏感度分析看不見這組歧見，
    引擎會單方面宣告使用者逾期 —— 正是大綱 §6.2 最嚴重的誤判方向。
    """
    report = screen(
        facts(
            complaint_date=date(2024, 1, 7),
            complaint_received_date=date(2024, 1, 7),
            business_replied=False,
            reply_received_date=None,
            business_reply_date=None,
            application_date=date(2024, 4, 8),
        )
    )
    assert report.by_code("R05").verdict is Verdict.DISPUTED


def test_逾期文案必須告知不含國定假日():
    """KI-01 的第二層：國定假日攔不到，只能靠文案補。"""
    report = screen(
        facts(
            complaint_date=date(2024, 1, 1),
            complaint_received_date=date(2024, 1, 1),
            business_replied=True,
            reply_received_date=date(2024, 2, 15),
            business_reply_date=date(2024, 2, 15),
            application_date=date(2024, 4, 5),
        )
    )
    result = report.by_code("R05")
    assert result.verdict is Verdict.BLOCKED
    assert "國定假日" in result.remedy


def test_有爭議文案也必須告知不含國定假日():
    report = screen(
        facts(
            complaint_date=date(2024, 4, 1),
            complaint_received_date=date(2024, 4, 1),
            business_replied=False,
            reply_received_date=None,
            business_reply_date=None,
            application_date=date(2024, 7, 1),
        )
    )
    result = report.by_code("R05")
    assert result.verdict is Verdict.DISPUTED
    assert "國定假日" in result.remedy


def test_兩種認定結論一致時不降級():
    report = screen(facts(application_date=date(2024, 3, 1)))
    assert report.by_code("R05").verdict is Verdict.CLEAR


def test_非日期規則不受敏感度分析影響():
    report = screen(facts(prior_evaluation=PriorEvaluation.REJECTED))
    assert report.by_code("R07").verdict is Verdict.BLOCKED


# —— 串接：R08 與 §23 V 的互動 ——


def test_調解成立則R08有障礙():
    report = screen(
        facts(
            proceedings=(
                Proceeding(ProceedingKind.MEDIATION_OTHER, ProceedingStatus.CONCLUDED, date(2024, 2, 1), True),
            )
        )
    )
    assert report.by_code("R08").verdict is Verdict.BLOCKED


def test_調解不成立則R08通過且R05取得新視窗():
    report = screen(
        facts(
            has_complained=False,
            complaint_date=None,
            complaint_received_date=None,
            business_replied=None,
            reply_received_date=None,
            business_reply_date=None,
            application_date=date(2024, 4, 30),
            proceedings=(
                Proceeding(ProceedingKind.MEDIATION_OTHER, ProceedingStatus.FAILED, date(2024, 3, 1)),
            ),
        )
    )
    assert report.by_code("R08").verdict is Verdict.CLEAR
    assert report.by_code("R05").computed["deadlines"]["§23 V"] == date(2024, 4, 30)


# —— 報告本身 ——


def test_報告保留所用的法規參數():
    report = screen(facts())
    assert report.params is DEFAULT_PARAMS


def test_未知代碼查詢會報錯():
    with pytest.raises(KeyError):
        screen(facts()).by_code("R99")
