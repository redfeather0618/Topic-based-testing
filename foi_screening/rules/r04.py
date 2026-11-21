"""R04 申訴處理尚未逾三十日。

金保法 §24 II 四：「向金融服務業提出申訴後，金融服務業**處理申訴中**尚未逾三十日。」

金保法 §13 II：「金融服務業應於收受申訴之日起三十日內為適當之處理，並將處理結果
回覆提出申訴之金融消費者；金融消費者**不接受處理結果者**或金融服務業逾上述期限
不為處理者，金融消費者得…申請評議。」

⚠️ 本款的核心是「處理申訴中」，不是單純的天數比大小。
   業者一旦回覆處理結果，申訴就不在「處理中」，申請人依 §13 II
   即可以「不接受處理結果」為由立刻申請評議，不必等滿三十日。
   把本款寫成 `申請日 - 申訴日 < 30` 會錯誤擋下這類申請人。

期間計算依民法 §120（始日不算入）；屆滿日當天提出仍屬「尚未逾三十日」。
"""

from __future__ import annotations

from functools import partial

from ..facts import ApplicationFacts, RuleFacts
from ..params import LegalParams
from ..periods import add_days
from ..results import RuleResult, Verdict
from ._common import insufficient

CODE = "R04"
NAME = "申訴處理尚未逾三十日"
LEGAL_BASIS = ("金保法§24 II 四", "金保法§13 II", "民法§120")

_insufficient = partial(insufficient, CODE, NAME, LEGAL_BASIS)


def check(facts: ApplicationFacts | RuleFacts, params: LegalParams) -> RuleResult:
    if facts.has_complained is None:
        return _insufficient(
            "你尚未填答是否已向金融服務業申訴，無法判斷此項。",
            "請填寫 F07「是否已向金融服務業申訴」。",
        )

    if facts.has_complained is False:
        # 本款以「向金融服務業提出申訴後」為前提。未申訴者由 R03 處理。
        return RuleResult(
            code=CODE,
            name=NAME,
            verdict=Verdict.CLEAR,
            reason="你尚未提出申訴，本款以「申訴後」為前提，故不成立。真正的障礙在 R03。",
            legal_basis=LEGAL_BASIS,
        )

    if facts.business_replied is None:
        return _insufficient(
            "你尚未填答業者是否已回覆申訴，無法判斷申訴是否仍在處理中。",
            "請填寫 F09「業者是否已回覆你的申訴」。",
        )

    if facts.business_replied is True:
        # 業者已回覆 → 申訴不在「處理申訴中」→ 本款不成立，與經過幾天無關。
        return RuleResult(
            code=CODE,
            name=NAME,
            verdict=Verdict.CLEAR,
            reason=(
                "業者已回覆申訴處理結果，申訴已不在「處理中」，本款不成立。"
                "依 §13 II，你可以不接受處理結果為由直接申請評議，不必等滿三十日。"
            ),
            legal_basis=LEGAL_BASIS,
        )

    if facts.complaint_received_date is None:
        return _insufficient(
            "業者尚未回覆，需要業者收受申訴日才能計算三十日期限，但你尚未填答。",
            "請確認業者實際收受申訴日（非 F08 提出日）；未確認時不推估。",
        )

    if facts.application_date is None:
        return _insufficient("尚未提供申請日期。", "請確認本次評議申請日期。")

    deadline = add_days(facts.complaint_received_date, params.business_processing_days, params)
    computed = {
        "complaint_received_date": facts.complaint_received_date,
        "deadline": deadline,
        "days_to_wait": max((deadline - facts.application_date).days, 0),
    }

    if facts.application_date <= deadline:
        days_to_wait = computed["days_to_wait"]
        return RuleResult(
            code=CODE,
            name=NAME,
            verdict=Verdict.BLOCKED,
            reason=(
                f"業者尚未回覆，而申訴的三十日法定處理期間要到 {deadline} 才屆滿，"
                f"目前仍在「處理申訴中」。"
            ),
            remedy=(
                f"請再等 {days_to_wait} 天，於 {deadline} 之後再提出評議申請；"
                "若業者在期限內回覆且你不接受該結果，收到回覆後即可立刻申請。"
                f"（本工具的期限計算不含國定假日；若 {deadline} 前後有連假，"
                "三十日期限可能再往後一兩天，建議多留幾天緩衝再送件。）"
            ),
            correctable=True,
            legal_basis=LEGAL_BASIS,
            computed=computed,
        )

    return RuleResult(
        code=CODE,
        name=NAME,
        verdict=Verdict.CLEAR,
        reason=f"申訴的三十日法定處理期間已於 {deadline} 屆滿，業者仍未回覆，本款不成立。",
        legal_basis=LEGAL_BASIS,
        computed=computed,
    )
