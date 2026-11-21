"""條文對照的可審查性 —— 大綱 §6.0 第 1 項。

「每條規則對到法條哪一款，逐條人工複核。這是主要保證。」
本檔確保那份清單可以自動產出、不會有規則漏標出處。
"""

import pytest

# 每一碼都要跑得出結果，故用全部欄位都填妥的那份申請
from conftest import complete_facts as facts

from foi_screening import screen
from foi_screening.engine import ALL_CODES, STATUTORY_CLAUSE
from foi_screening.params import DEFAULT_PARAMS, PROVENANCE, LegalParams


@pytest.mark.parametrize("code", ALL_CODES)
def test_每一碼都帶出條文依據(code):
    result = screen(facts()).by_code(code)
    assert result.legal_basis
    assert all(basis.strip() for basis in result.legal_basis)


@pytest.mark.parametrize("code", ALL_CODES)
def test_每一碼都引用金保法第二十四條第二項的對應款(code):
    """每一碼都必須回得到 §24 II 的某一款。

    R01 拆成 R01-1／R01-2 後，碼與款是多對一。對應關係由
    `engine.STATUTORY_CLAUSE` 明示，不再從碼的數字推導。
    """
    clause = "一二三四五六七八九"[STATUTORY_CLAUSE[code] - 1]
    result = screen(facts()).by_code(code)
    assert f"金保法§24 II {clause}" in result.legal_basis


def test_九款無一遺漏():
    """多對一之後仍須確保九款全被涵蓋，不得有哪一款沒人負責。"""
    assert set(STATUTORY_CLAUSE.values()) == set(range(1, 10))


def test_對應表與碼表一致():
    assert set(STATUTORY_CLAUSE) == set(ALL_CODES)


@pytest.mark.parametrize("code", ALL_CODES)
def test_每一碼都有面向使用者的說明(code):
    assert screen(facts()).by_code(code).reason


def test_每個法規參數都登記了出處與查證狀態():
    fields = {f.name for f in LegalParams.__dataclass_fields__.values()}
    assert fields == set(PROVENANCE)


def test_未經查證的認定必須附上說明():
    """verified=False 代表是依文義所做的認定，報告需揭露，因此 note 不得留空。"""
    unverified = {k: v for k, v in PROVENANCE.items() if not v.verified}
    assert unverified, "至少應誠實標記出未經查證的認定"
    for name, provenance in unverified.items():
        assert provenance.note.strip(), f"{name} 未說明其未經查證之處"


def test_預設參數與條文明文的數字一致():
    assert DEFAULT_PARAMS.business_processing_days == 30
    assert DEFAULT_PARAMS.filing_window_days == 60
    assert DEFAULT_PARAMS.mediation_failure_window_days == 60
