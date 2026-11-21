"""R08 已有終局處理。

金保法 §24 II 八：「申請評議事件已經法院判決**確定**，或已**成立**調處、評議、
和解、調解或仲裁。」

條文要的是判決「確定」與程序「成立」：
  CONCLUDED → 命中本款
  PENDING   → 判決尚未確定、程序進行中，不命中
  FAILED    → 不成立，不命中；若為調處或調解，另依 §23 V 取得新的申請視窗（見 r05）

⚠️ 大綱 §5.1：本款依使用者自陳，無從查證。使用者可能不知道自己的案子
   算不算「已成立調解」，輸出必須標為「依你的填答」。
"""

from __future__ import annotations

from functools import partial

from ..facts import ApplicationFacts, RuleFacts, ProceedingStatus
from ..params import LegalParams
from ..results import RuleResult, Verdict
from ._common import insufficient

CODE = "R08"
NAME = "已有終局處理"
LEGAL_BASIS = ("金保法§24 II 八",)

#: 本款依使用者自陳，評議中心以外無從查證。
_insufficient = partial(insufficient, CODE, NAME, LEGAL_BASIS, self_declared=True)


def check(facts: ApplicationFacts | RuleFacts, params: LegalParams) -> RuleResult:
    if facts.proceedings is None:
        return _insufficient(
            "你尚未填答是否已有法院判決或其他爭議處理程序，無法判斷此項。",
            "請填寫 F12「是否已有法院判決／和解／調解／調處／仲裁」，並逐項註明是進行中、已成立還是不成立。",
        )

    concluded = [p for p in facts.proceedings
        if p.status is ProceedingStatus.CONCLUDED and p.covers_current_case is True]
    unknown_scope = any(p.status is ProceedingStatus.CONCLUDED
        and p.covers_current_case is None for p in facts.proceedings)

    if concluded and facts.application_date is None:
        return _insufficient("尚未提供本次評議提出日期，無法確認程序是否已於當時成立。",
            "請確認本次評議提出日；不得由目前成立狀態回推當時狀態。")
    if facts.application_date and any(p.date is None for p in concluded):
        return _insufficient("本 Case 的既有程序成立日期未確認，無法核對評議提出時點。",
            "請確認成立／確定日期；不得把評議提出後的程序回溯套用。")
    if concluded:
        names = "、".join(p.kind.value for p in concluded)
        return RuleResult(
            code=CODE,
            name=NAME,
            verdict=Verdict.BLOCKED,
            reason=f"依你的填答，本事件已有終局處理（{names}），構成 §24 II 八的不受理事由。",
            remedy="本款無從補正。若該程序處理的爭議標的與本次申請不同，請確認兩者確實可分。",
            correctable=False,
            legal_basis=LEGAL_BASIS,
            self_declared=True,
            computed={"concluded": tuple(p.kind.value for p in concluded)},
        )

    if unknown_scope:
        return _insufficient("既有成立／確定程序是否涵蓋本 Case 尚未確認。",
            "請人工確認既有程序的事件及請求範圍；不得套用同保單的其他事故。")

    return RuleResult(
        code=CODE,
        name=NAME,
        verdict=Verdict.CLEAR,
        reason="依你的填答，本事件尚無已確定的法院判決，也沒有已成立的調處、評議、和解、調解或仲裁。",
        legal_basis=LEGAL_BASIS,
        self_declared=True,
    )
