"""R01-1 申請不合程式 —— 形式檢查層。

金保法 §24 II 一：「申請不合程式。」
但書：「其情形可以補正者，爭議處理機構應通知金融消費者於合理期限內補正。」

評議程序辦法 §13：申請評議應填具申請書，載明當事人名稱及基本資料、請求標的、
事實、理由及申訴未獲妥適處理之情形，並檢具相關文件或資料。
評議程序辦法 §14：申請書不合法定程式者，應酌定合理期間通知申請人補正。

**本規則採「準備清單」語意** —— 使用者多半尚未備妥文件，「還沒做」不等於障礙：

    欄位留空 → INSUFFICIENT（待辦清單）
    明確為否 → BLOCKED 且 correctable=True（確定缺，補齊即可）

**「不適用」與「該有卻沒有」必須分開**：沒有代理人的人不該因為
沒附委任狀而被判缺件。適用集合由情境題算出，見 `_applicable()`。
"""

from __future__ import annotations

from functools import partial

from ..facts import ApplicationFacts, ApplicationReadiness, SubmissionMethod
from ..params import LegalParams
from ..results import RuleResult, Verdict
from ._common import insufficient

CODE = "R01-1"
NAME = "申請不合程式 —— 形式檢查層"
LEGAL_BASIS = ("金保法§24 II 一", "評議程序辦法§13", "評議程序辦法§14")

#: 一律必備的記載事項與文件：欄位名 → 面向使用者的名稱。
_ALWAYS_REQUIRED = {
    "has_application_form": "評議申請書",
    "has_claim_stated": "請求標的（載明請求內容與金額）",
    "has_facts_and_reasons": "事實及理由",
    "is_signed": "申請人簽名或蓋章",
    "has_id_copy": "身分證明文件（自然人：身分證正反面影本；法人：登記證明文件）",
}

#: 本規則無從查證使用者是否真的備妥，一律標為自陳。
_insufficient = partial(insufficient, CODE, NAME, LEGAL_BASIS, self_declared=True)


def _unanswered_context(readiness: ApplicationReadiness) -> list[str]:
    """尚未回答的必答情境題。情境題未答就算不出適用集合。"""
    missing = []
    if readiness.submission_method is None:
        missing.append("F17 送件方式（紙本或線上）")
    if readiness.has_legal_representative is None:
        missing.append("F18 是否有法定代理人")
    elif readiness.has_legal_representative is True and (
        readiness.legal_rep_applying_alone is None
    ):
        missing.append("F18a 法定代理人是否單方面申請")
    if readiness.has_appointed_agent is None:
        missing.append("F19 是否有委任代理人")
    if (
        readiness.submission_method is SubmissionMethod.PAPER
        and readiness.respondent_count is None
    ):
        missing.append("F20 相對人人數")
    return missing


def _applicable(readiness: ApplicationReadiness) -> dict[str, str]:
    """依情境題算出要檢查的項目：欄位名 → 面向使用者的名稱。"""
    items = dict(_ALWAYS_REQUIRED)
    if readiness.has_legal_representative is True:
        items["has_legal_rep_proof"] = "法定代理人證明文件"
    if (
        readiness.has_legal_representative is True
        and readiness.legal_rep_applying_alone is True
    ):
        items["has_other_party_consent"] = "他方同意書"
    if readiness.has_appointed_agent is True:
        items["has_power_of_attorney"] = "委任狀"
    if readiness.submission_method is SubmissionMethod.PAPER:
        items["has_copies_for_respondents"] = (
            f"繕本及證據資料（{readiness.respondent_count} 份，按相對人人數）"
        )
    return items


def check(facts: ApplicationFacts, params: LegalParams) -> RuleResult:
    readiness = facts.readiness
    empty: dict = {"applicable": [], "missing": [], "unanswered": []}

    if readiness is None:
        return _insufficient(
            "你尚未填答申請書的齊備情形，無法判斷此項。",
            "請填寫 F17–F21：送件方式、有無代理人，以及申請書與應附文件的準備情形。",
            computed=empty,
        )

    unanswered_context = _unanswered_context(readiness)
    if unanswered_context:
        return _insufficient(
            "還有幾個問題沒回答，無法判斷哪些文件對你適用。",
            "請先回答：" + "、".join(unanswered_context) + "。",
            computed=empty,
        )

    if (
        readiness.submission_method is SubmissionMethod.PAPER
        and readiness.respondent_count is not None
        and readiness.respondent_count < 1
    ):
        return _insufficient(
            f"相對人人數填了 {readiness.respondent_count}，這不合理。",
            "請更正 F20「相對人人數」：相對人至少一人，否則不成其為金融消費爭議。",
            computed=empty,
        )

    items = _applicable(readiness)
    labels = list(items.values())
    unanswered = [
        label for field, label in items.items() if getattr(readiness, field) is None
    ]
    if unanswered:
        return _insufficient(
            "申請書與應附文件還有項目沒回答，無法判斷此項。",
            "請逐項確認是否已備妥：" + "、".join(unanswered) + "。",
            computed={"applicable": labels, "missing": [], "unanswered": unanswered},
        )

    missing = [
        label for field, label in items.items() if getattr(readiness, field) is False
    ]
    computed = {"applicable": labels, "missing": missing, "unanswered": []}

    if missing:
        return RuleResult(
            code=CODE,
            name=NAME,
            verdict=Verdict.BLOCKED,
            reason=(
                "依你的填答，申請書或應附文件還缺以下項目："
                + "、".join(missing)
                + "。依評議程序辦法 §13，這些是申請評議應載明或應檢具的內容。"
            ),
            remedy=(
                "請在送件前補齊上列項目。依金保法 §24 II 但書與評議程序辦法 §14，"
                "申請不合程式屬「可以補正」的情形 —— 即使先送出，爭議處理機構也會"
                "通知你於合理期限內補正，不是不能申請。"
            ),
            correctable=True,
            legal_basis=LEGAL_BASIS,
            self_declared=True,
            computed=computed,
        )

    return RuleResult(
        code=CODE,
        name=NAME,
        verdict=Verdict.CLEAR,
        reason=(
            f"依你的填答，本層檢查的 {len(labels)} 項都已備妥。"
            "但申請書的其餘記載事項（當事人基本資料與可即時送達之地址、"
            "申訴經過與未獲妥適處理之情形、是否同意試行調處）本工具尚未檢查，"
            "請自行對照官方申請書確認。"
        ),
        legal_basis=LEGAL_BASIS,
        self_declared=True,
        computed=computed,
    )
