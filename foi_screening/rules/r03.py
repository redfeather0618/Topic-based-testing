"""R03 未先向金融服務業申訴。

金保法 §24 II 三：「未先向金融服務業申訴。」

金保法 §13 II 前段：「金融消費者就金融消費爭議事件應先向金融服務業提出申訴…」
金保法 §13 II 後段：「金融消費者向爭議處理機構提出申訴者，爭議處理機構之金融消費者
                      服務部門應將該申訴移交金融服務業處理。」
                      —— 故經中心移交者亦屬已申訴，F07 應填 True。
"""

from __future__ import annotations

from functools import partial

from ..facts import ApplicationFacts, RuleFacts
from ..params import LegalParams
from ..results import RuleResult, Verdict
from ._common import insufficient

CODE = "R03"
NAME = "未先向金融服務業申訴"
LEGAL_BASIS = ("金保法§24 II 三", "金保法§13 II")

_insufficient = partial(insufficient, CODE, NAME, LEGAL_BASIS)


def check(facts: ApplicationFacts | RuleFacts, params: LegalParams) -> RuleResult:
    if (facts.complaint_date and facts.application_date
            and facts.complaint_date > facts.application_date):
        return _insufficient("申訴日期晚於本次評議提出日，不能認定已先申訴。",
            "請核對申訴與評議提出時點，以及本 Case 的有效申訴範圍。")
    if facts.has_complained is None:
        return _insufficient(
            "你尚未填答是否已向金融服務業提出申訴，無法判斷此項。",
            "請填寫 F07「是否已向金融服務業申訴」。若你是向評議中心提出申訴並經其移交業者處理，同樣算已申訴。",
        )

    if facts.has_complained is False:
        return RuleResult(
            code=CODE,
            name=NAME,
            verdict=Verdict.BLOCKED,
            reason="依金保法 §13 II，須先向金融服務業提出申訴，才能向評議中心申請評議。你目前尚未申訴。",
            remedy="請先向該金融服務業正式提出申訴，並保留申訴證明；業者處理後才能申請評議。",
            correctable=True,
            legal_basis=LEGAL_BASIS,
        )

    return RuleResult(
        code=CODE,
        name=NAME,
        verdict=Verdict.CLEAR,
        reason="你已先向金融服務業提出申訴，符合 §13 II 的前置程序。",
        legal_basis=LEGAL_BASIS,
    )
