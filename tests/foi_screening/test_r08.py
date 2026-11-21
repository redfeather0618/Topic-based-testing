"""R08 已有終局處理 —— 金保法 §24 II 八。

「申請評議事件已經法院判決確定，或已成立調處、評議、和解、調解或仲裁。」

關鍵：條文要的是判決「確定」與程序「成立」。進行中或不成立都不是本款情形。
"""

from datetime import date

import pytest
from conftest import facts as base_facts

from foi_screening.facts import (
    ApplicationFacts,
    Proceeding,
    ProceedingKind,
    ProceedingStatus,
)
from foi_screening.params import DEFAULT_PARAMS
from foi_screening.results import Verdict
from foi_screening.rules import r08

ALL_KINDS = list(ProceedingKind)


def facts(*proceedings: Proceeding) -> ApplicationFacts:
    return _facts(proceedings)


def _facts(proceedings: tuple[Proceeding, ...] | None) -> ApplicationFacts:
    """`None` 代表 F12 沒填，空 tuple 代表「都沒有」—— 兩者輸出不同。"""
    return base_facts(proceedings=proceedings)


def test_沒有任何程序_判定通過():
    assert r08.check(facts(), DEFAULT_PARAMS).verdict is Verdict.CLEAR


@pytest.mark.parametrize("kind", ALL_KINDS)
def test_任一程序已成立或判決確定_判定有障礙(kind):
    p = Proceeding(kind=kind, status=ProceedingStatus.CONCLUDED, date=date(2024, 3, 1), covers_current_case=True)
    assert r08.check(facts(p), DEFAULT_PARAMS).verdict is Verdict.BLOCKED


@pytest.mark.parametrize("kind", ALL_KINDS)
def test_程序進行中_不觸發本款(kind):
    """法院判決尚未確定、調解尚在進行，都不是 §24 II 八的情形。"""
    p = Proceeding(kind=kind, status=ProceedingStatus.PENDING, date=None)
    assert r08.check(facts(p), DEFAULT_PARAMS).verdict is Verdict.CLEAR


@pytest.mark.parametrize("kind", ALL_KINDS)
def test_程序不成立_不觸發本款(kind):
    """調解「不成立」與「成立」結果相反，§23 V 反而給了新的申請視窗。"""
    p = Proceeding(kind=kind, status=ProceedingStatus.FAILED, date=date(2024, 3, 1))
    assert r08.check(facts(p), DEFAULT_PARAMS).verdict is Verdict.CLEAR


def test_多項程序中只要有一項成立即有障礙():
    result = r08.check(
        facts(
            Proceeding(ProceedingKind.MEDIATION_OTHER, ProceedingStatus.FAILED, date(2024, 2, 1)),
            Proceeding(ProceedingKind.ARBITRATION, ProceedingStatus.CONCLUDED, date(2024, 3, 1), True),
        ),
        DEFAULT_PARAMS,
    )
    assert result.verdict is Verdict.BLOCKED


def test_有障礙時說明是哪一種程序():
    result = r08.check(
        facts(Proceeding(ProceedingKind.ARBITRATION, ProceedingStatus.CONCLUDED, date(2024, 3, 1), True)),
        DEFAULT_PARAMS,
    )
    assert "仲裁" in result.reason


def test_未填答_判定資料不足():
    result = r08.check(_facts(None), DEFAULT_PARAMS)
    assert result.verdict is Verdict.INSUFFICIENT
    assert "F12" in result.remedy


def test_不可補正且標記為使用者自陳():
    result = r08.check(
        facts(Proceeding(ProceedingKind.COURT_JUDGMENT, ProceedingStatus.CONCLUDED, date(2024, 3, 1), True)),
        DEFAULT_PARAMS,
    )
    assert result.correctable is False
    assert result.self_declared is True


def test_帶出條文依據():
    result = r08.check(facts(), DEFAULT_PARAMS)
    assert "金保法§24 II 八" in result.legal_basis
    assert result.code == "R08"
