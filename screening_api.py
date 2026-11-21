from __future__ import annotations

from datetime import date as Date
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from foi_screening import (
    ApplicationFacts,
    PriorEvaluation,
    Proceeding,
    ProceedingKind,
    ProceedingStatus,
    screen_rule,
)

router = APIRouter()


class ProceedingInput(BaseModel):
    """案件曾參與的其他程序；未知值必須省略或填 null。"""

    kind: ProceedingKind
    status: ProceedingStatus
    date: Date | None = None
    covers_current_case: bool | None = None


class ScreeningRequest(BaseModel):
    """五碼引擎輸入；None 代表尚未提供，不能當成否。"""

    application_date: Date = Field(default_factory=Date.today)
    has_complained: bool | None = None
    complaint_date: Date | None = None
    complaint_received_date: Date | None = None
    business_replied: bool | None = None
    business_reply_date: Date | None = None
    reply_received_date: Date | None = None
    center_received_date: Date | None = None
    prior_evaluation: PriorEvaluation | None = None
    proceedings: list[ProceedingInput] | None = None


def _facts(case: ScreeningRequest) -> ApplicationFacts:
    proceedings = None
    if case.proceedings is not None:
        proceedings = tuple(
            Proceeding(
                kind=item.kind,
                status=item.status,
                date=item.date,
                covers_current_case=item.covers_current_case,
            )
            for item in case.proceedings
        )
    return ApplicationFacts(
        application_date=case.application_date,
        has_complained=case.has_complained,
        complaint_date=case.complaint_date,
        complaint_received_date=case.complaint_received_date,
        business_replied=case.business_replied,
        business_reply_date=case.business_reply_date,
        reply_received_date=case.reply_received_date,
        center_received_date=case.center_received_date,
        prior_evaluation=case.prior_evaluation,
        proceedings=proceedings,
    )


def _serialize(result: Any) -> dict[str, Any]:
    return {
        "code": result.code,
        "name": result.name,
        "verdict": result.verdict.value,
        "icon": result.icon,
        "reason": result.reason,
        "remedy": result.remedy,
        "legal_basis": list(result.legal_basis),
        "correctable": result.correctable,
        "self_declared": result.self_declared,
        "computed": result.computed,
    }


@router.post("/api/v1/screening")
def screen_case(case: ScreeningRequest) -> dict[str, Any]:
    """依組長引擎執行已開放的 R03、R04、R05、R07、R08 五碼。"""
    facts = _facts(case)
    codes = ("R03", "R04", "R05", "R07", "R08")
    return {
        "api_status": "success",
        "scope": list(codes),
        "results": [_serialize(screen_rule(code, facts)) for code in codes],
        "notice": (
            "結果只涵蓋五碼；資料不足及自陳事實會依引擎標示。"
            "本工具不構成法律意見，實際受理與否以評議中心決定為準。"
        ),
    }


