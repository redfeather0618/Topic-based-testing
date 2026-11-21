"""R05 申請已逾法定期限。

金保法 §24 II 五：「申請已逾法定期限。」

法定期限有兩條來源：

金保法 §13 II：「…金融消費者不接受處理結果者或金融服務業逾上述期限不為處理者，
金融消費者得於**收受處理結果或期限屆滿之日起六十日內**，向爭議處理機構申請評議…」

金保法 §23 V：「金融消費者已依其他法律規定**調處或調解不成立**者，得於調處或
調解不成立之日起**六十日內**申請評議。」

⚠️ 本規則不使用「爭議發生日」與「知悉爭議之日」，理由見 `facts.py` 的模組說明。

**起算點**：
  業者於三十日內回覆 → 起算 = 收受處理結果之日
  業者未於三十日內處理 → 起算 = 三十日期限屆滿之日
  業者逾三十日之後才回覆 → 仍以屆滿日起算

最後一種情形 §13 II 未明文，已依評議中心實際案例確認（見 `docs/legal_basis.md`
§四之一），故直接實作，不另設參數。

**多路徑取較寬**：任一條法定期限尚未屆至，即不構成本款。
"""

from __future__ import annotations

from datetime import date
from functools import partial

from ..facts import MEDIATION_KINDS, ApplicationFacts, RuleFacts, ProceedingStatus
from ..params import LegalParams
from ..periods import add_days, is_expired
from ..results import RuleResult, Verdict
from ._common import insufficient

CODE = "R05"
NAME = "申請已逾法定期限"
LEGAL_BASIS = ("金保法§24 II 五", "金保法§13 II", "金保法§23 V", "民法§120")

PATH_COMPLAINT = "§13 II"
PATH_MEDIATION = "§23 V"

_insufficient = partial(insufficient, CODE, NAME, LEGAL_BASIS)


def _complaint_start_date(
    facts: ApplicationFacts | RuleFacts, params: LegalParams
) -> tuple[date | None, str | None]:
    """回傳 §13 II 路徑的起算日，或 (None, 缺少的欄位說明)。"""
    has_complained = facts.has_complained
    business_replied = facts.business_replied
    if facts.center_received_date is not None:
        # Historical R05 observes center receipt. Explicit events can postdate
        # submission-time bools; derive only this rule's state, never mutate facts.
        if any(d is not None and d <= facts.center_received_date for d in (
            facts.complaint_date, facts.complaint_received_date,
            facts.business_reply_date, facts.reply_received_date,
        )):
            has_complained = True
        if any(d is not None and d <= facts.center_received_date for d in (
            facts.business_reply_date, facts.reply_received_date,
        )):
            business_replied = True

    if has_complained is None:
        return None, "請確認是否已就本案申訴。"
    if has_complained is False:
        return None, None  # 未申訴：本路徑不存在，由 R03 處理

    if facts.complaint_received_date is None:
        return None, "請填寫 業者實際收受申訴日（非 F08 提出日）。"

    expiry = add_days(facts.complaint_received_date, params.business_processing_days, params)

    if business_replied is None:
        return None, "請確認業者是否已回覆，未填不能視為未回覆。"
    if business_replied is False:
        # 已明確確認業者未回覆。
        return expiry, None

    if facts.reply_received_date is None:
        return None, (
            "請填寫 F09 的「你收到業者回覆的日期」—— 以你實際收到或看到的日期為準，"
            "不是業者信件上的日期；若為掛號，可參考簽收日。"
        )

    if facts.business_reply_date is None:
        return None, "請確認業者實際回覆處理結果日期；不得以申請人收受日推認。"

    if facts.business_reply_date <= expiry:
        # 業者於法定期間內回覆 → 自收受處理結果之日起算
        return facts.reply_received_date, None

    # 業者逾三十日之後才回覆 —— 期限屆滿即起算，事後回覆不重新起算
    return expiry, None


def _mediation_start_date(facts: ApplicationFacts | RuleFacts) -> tuple[date | None, str | None]:
    """回傳已知最晚起算日與缺漏說明；部分日期未知時兩者可同時存在。"""
    if facts.proceedings is None:
        return None, "請確認其他程序；未填不等於沒有調處或調解不成立的紀錄。"
    if not facts.proceedings:
        return None, None

    failed = [
        p
        for p in facts.proceedings
        if p.kind in MEDIATION_KINDS and p.status is ProceedingStatus.FAILED
        and p.covers_current_case is not False
    ]
    if not failed:
        return None, None

    known_dates = [p.date for p in failed if p.date is not None]
    missing = "請在 F12 填寫調處或調解「不成立之日」。" if len(known_dates) < len(failed) else None
    return max(known_dates, default=None), missing


def check(facts: ApplicationFacts | RuleFacts, params: LegalParams) -> RuleResult:
    comparison_date = facts.center_received_date or facts.application_date
    if comparison_date is None:
        return _insufficient("尚未提供中心收文或預計申請日期。", "請確認中心實際收文日；申請前估算則提供預計提出日。")
    basis = "center_received_date" if facts.center_received_date else "application_date_estimate"
    endpoint_name = "中心收文日" if facts.center_received_date else "預計提出日（申請前估算）"
    endpoint = {"comparison_date": comparison_date, "comparison_basis": basis}
    start_dates: dict[str, date] = {}
    missing: list[str] = []

    complaint_start, complaint_missing = _complaint_start_date(facts, params)
    if complaint_start is not None:
        start_dates[PATH_COMPLAINT] = complaint_start
    elif complaint_missing:
        missing.append(complaint_missing)

    mediation_start, mediation_missing = _mediation_start_date(facts)
    if mediation_start is not None:
        start_dates[PATH_MEDIATION] = mediation_start
    if mediation_missing:
        missing.append(mediation_missing)

    if not start_dates:
        if missing:
            return _insufficient("申請期限的事實尚未確認。", " ".join(missing))
        return RuleResult(
            code=CODE,
            name=NAME,
            verdict=Verdict.CLEAR,
            reason=(
                "你尚未申訴、也沒有調處或調解不成立的紀錄，六十日申請期間尚未起算，"
                "不可能逾期。真正的障礙在 R03。"
            ),
            legal_basis=LEGAL_BASIS,
            computed={"start_dates": {}, "deadlines": {}, "latest_deadline": None, **endpoint},
        )

    window = {
        PATH_COMPLAINT: params.filing_window_days,
        PATH_MEDIATION: params.mediation_failure_window_days,
    }
    deadlines = {
        path: add_days(start, window[path], params) for path, start in start_dates.items()
    }
    latest = max(deadlines.values())
    computed = {"start_dates": start_dates, "deadlines": deadlines, "latest_deadline": latest, **endpoint}

    if is_expired(comparison_date, latest):
        if missing:
            return _insufficient("已知期限已過，但仍有未確認的其他起算路徑。", " ".join(missing),
                computed=computed)
        detail = "、".join(f"依 {path} 為 {d.isoformat()}" for path, d in deadlines.items())
        return RuleResult(
            code=CODE,
            name=NAME,
            verdict=Verdict.BLOCKED,
            reason=(
                f"你的申請期限已屆滿（{detail}），而{endpoint_name}為 "
                f"{comparison_date.isoformat()}，已逾法定期限。"
            ),
            remedy=(
                "本款無從補正。若你認為起算日有誤（例如實際收受業者回覆的日期較晚），"
                "請重新確認日期。另外，本工具的期限計算只把星期六與星期日當作休息日，"
                "不含國定假日 —— 若上列末日前後有春節、清明等連假，依民法 §122 "
                "真正的末日可能比這裡顯示的更晚，你未必已經逾期。"
                "期限的認定最終以評議中心為準，仍建議儘早送件。"
            ),
            correctable=False,
            legal_basis=LEGAL_BASIS,
            computed=computed,
        )

    return RuleResult(
        code=CODE,
        name=NAME,
        verdict=Verdict.CLEAR,
        reason=(
            f"你的申請期限至 {latest.isoformat()} 屆滿，{endpoint_name} "
            f"{comparison_date.isoformat()} 仍在期限內。"
        ),
        legal_basis=LEGAL_BASIS,
        computed=computed,
    )
