"""R07 曾依本法申請評議而不成立。

金保法 §24 II 七：「曾依本法申請評議而不成立。」

正式 Codebook 將同一事件先前申請後「撤回」亦納入本款；保留獨立狀態。曾申請而評議成立、或曾申請尚無結果，
都不是本款情形。

⚠️ 大綱 §5.1：本款依使用者自陳，評議中心以外無從查證，
   輸出必須標為「依你的填答」而非「經查證」。
"""

from __future__ import annotations

from functools import partial

from ..facts import ApplicationFacts, RuleFacts, PriorEvaluation
from ..params import LegalParams
from ..results import RuleResult, Verdict
from ._common import insufficient

CODE = "R07"
NAME = "曾依本法申請評議而不成立"
LEGAL_BASIS = ("金保法§24 II 七",)

#: 本款依使用者自陳，評議中心以外無從查證。
_insufficient = partial(insufficient, CODE, NAME, LEGAL_BASIS, self_declared=True)


def check(facts: ApplicationFacts | RuleFacts, params: LegalParams) -> RuleResult:
    prior = facts.prior_evaluation

    if prior is None:
        return _insufficient(
            "你尚未填答是否曾就同一事件申請過評議，無法判斷此項。",
            "請填寫 F11「是否曾就同一事件申請過評議、結果為何」。",
        )

    if prior in (PriorEvaluation.REJECTED, PriorEvaluation.WITHDRAWN):
        return RuleResult(
            code=CODE,
            name=NAME,
            verdict=Verdict.BLOCKED,
            reason=f"依你的填答，同一事件{prior.value}，構成 §24 II 七的不受理事由。",
            remedy="本款無從補正。若你認為是不同事件，請確認前後兩次申請的爭議標的確實不同。",
            correctable=False,
            legal_basis=LEGAL_BASIS,
            self_declared=True,
        )

    return RuleResult(
        code=CODE,
        name=NAME,
        verdict=Verdict.CLEAR,
        reason=f"依你的填答（{prior.value}），不構成「曾依本法申請評議而不成立」。",
        legal_basis=LEGAL_BASIS,
        self_declared=True,
    )
