"""R01-1 申請不合程式 —— 形式檢查層。

評議程序辦法 §13 要求申請書「載明」記載事項並「檢具」文件；
§14 規定不合法定程式者應通知補正；金保法 §24 II 但書亦明文可補正。

本規則採「準備清單」語意（見 docs/specs/2026-09-14-r01-1-r09-1-design.md §2）：
  欄位留空 → INSUFFICIENT（你還沒做到那一步，這是待辦清單）
  明確為否 → BLOCKED 且 correctable=True（你確定缺，補齊即可）
"""

from conftest import facts, readiness

from foi_screening.facts import SubmissionMethod
from foi_screening.params import DEFAULT_PARAMS
from foi_screening.results import Verdict
from foi_screening.rules import r01_1


def check(**overrides):
    """跑一次 R01-1。預設是全部備妥的申請書，只覆寫要測的那個欄位。"""
    return r01_1.check(facts(readiness=readiness(**overrides)), DEFAULT_PARAMS)


# —— 未填答 ——


def test_整節未填為資料不足():
    # facts() 不帶 readiness，即 F17–F21 整節沒填
    result = r01_1.check(facts(), DEFAULT_PARAMS)
    assert result.verdict is Verdict.INSUFFICIENT
    assert result.remedy


def test_情境題未答時先問情境題而不誤報缺件():
    """送件方式未答就算不出適用集合，不能直接說文件缺了。"""
    result = check(submission_method=None)
    assert result.verdict is Verdict.INSUFFICIENT
    assert "F17" in result.remedy
    assert result.computed["missing"] == []


def test_有法定代理人時才追問是否單方申請():
    result = check(has_legal_representative=True, legal_rep_applying_alone=None)
    assert result.verdict is Verdict.INSUFFICIENT
    assert "F18a" in result.remedy


def test_必備項目未答為資料不足並列出未答項():
    result = check(has_id_copy=None)
    assert result.verdict is Verdict.INSUFFICIENT
    assert (
        "身分證明文件（自然人：身分證正反面影本；法人：登記證明文件）"
        in result.computed["unanswered"]
    )


# —— 全部備妥 ——


def test_全部備妥為無此障礙():
    result = check()
    assert result.verdict is Verdict.CLEAR
    assert result.computed["missing"] == []


def test_一律標示為依使用者自陳():
    assert check().self_declared is True


def test_一律帶出條文依據():
    basis = check().legal_basis
    assert "金保法§24 II 一" in basis
    assert "評議程序辦法§13" in basis


# —— 適用性 ——


def test_無代理人時不因缺委任狀而判缺件():
    result = check(has_appointed_agent=False, has_power_of_attorney=False)
    assert result.verdict is Verdict.CLEAR
    assert "委任狀" not in result.computed["applicable"]


def test_有委任代理人時缺委任狀即為有障礙():
    result = check(has_appointed_agent=True, has_power_of_attorney=False)
    assert result.verdict is Verdict.BLOCKED
    assert "委任狀" in result.computed["missing"]


def test_法定代理人單方申請時需他方同意書():
    result = check(
        has_legal_representative=True,
        legal_rep_applying_alone=True,
        has_legal_rep_proof=True,
        has_other_party_consent=False,
    )
    assert result.verdict is Verdict.BLOCKED
    assert "他方同意書" in result.computed["missing"]


def test_有法定代理人時缺證明文件即為有障礙():
    result = check(
        has_legal_representative=True,
        legal_rep_applying_alone=False,
        has_legal_rep_proof=False,
    )
    assert result.verdict is Verdict.BLOCKED
    assert "法定代理人證明文件" in result.computed["missing"]


def test_法定代理人非單方申請時不需他方同意書():
    result = check(
        has_legal_representative=True,
        legal_rep_applying_alone=False,
        has_legal_rep_proof=True,
    )
    assert result.verdict is Verdict.CLEAR
    assert "法定代理人證明文件" in result.computed["applicable"]
    assert "他方同意書" not in result.computed["applicable"]


def test_無法定代理人時不因缺他方同意書而判缺件():
    """矛盾填答的防呆：沒有法定代理人，就不該被要求他方同意書。

    _unanswered_context() 不會強制回答 legal_rep_applying_alone，
    且 ApplicationReadiness 無欄位驗證，故此組合可達。
    """
    result = check(
        has_legal_representative=False,
        legal_rep_applying_alone=True,
        has_other_party_consent=False,
    )
    assert result.verdict is Verdict.CLEAR
    assert "他方同意書" not in result.computed["applicable"]


def test_線上送件不檢查繕本():
    result = check(
        submission_method=SubmissionMethod.ONLINE, has_copies_for_respondents=False
    )
    assert result.verdict is Verdict.CLEAR


def test_紙本送件檢查繕本():
    result = check(
        submission_method=SubmissionMethod.PAPER,
        respondent_count=1,
        has_copies_for_respondents=False,
    )
    assert result.verdict is Verdict.BLOCKED
    assert any("繕本" in item for item in result.computed["missing"])


# —— 相對人人數 ——


def test_紙本送件未填相對人人數為資料不足():
    result = check(submission_method=SubmissionMethod.PAPER, respondent_count=None)
    assert result.verdict is Verdict.INSUFFICIENT
    assert "F20" in result.remedy


def test_相對人人數小於一視為填答錯誤():
    result = check(
        submission_method=SubmissionMethod.PAPER,
        respondent_count=0,
        has_copies_for_respondents=True,
    )
    assert result.verdict is Verdict.INSUFFICIENT
    assert "相對人" in result.remedy


def test_相對人人數本身不是判定項目():
    """人數只用來寫出繕本份數，不會多出一個獨立的檢查項目。

    注意不能用「標籤含『人數』」來斷言 —— 繕本標籤本身就寫著「按相對人人數」。
    """
    result = check(
        submission_method=SubmissionMethod.PAPER,
        respondent_count=2,
        has_copies_for_respondents=True,
    )
    assert result.verdict is Verdict.CLEAR
    # 5 項一律必備 + 1 項繕本，沒有第 7 項
    assert len(result.computed["applicable"]) == 6
    assert any("2 份" in item for item in result.computed["applicable"])


# —— 缺件 ——


def test_缺件時標為可補正且文案說明補齊即可():
    result = check(has_id_copy=False)
    assert result.verdict is Verdict.BLOCKED
    assert result.correctable is True
    assert "補正" in result.remedy


def test_缺件清單只列出適用且為否的項目():
    result = check(has_id_copy=False, is_signed=False, has_power_of_attorney=False)
    assert set(result.computed["missing"]) == {
        "身分證明文件（自然人：身分證正反面影本；法人：登記證明文件）",
        "申請人簽名或蓋章",
    }
