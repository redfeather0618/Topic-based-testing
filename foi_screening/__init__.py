"""金融消費評議 —— 申請前資格自我審查（階段 A 規則引擎）。

只覆蓋金保法第 24 條第 2 項九款中，能由條文、日期或形式核對直接判斷的七碼：
R01-1 申請不合程式（形式檢查層）、R03 未先申訴、R04 申訴處理尚未逾三十日、
R05 申請已逾法定期限、R07 曾依本法申請評議而不成立、R08 已有終局處理、
R09-1 其他主管機關規定之情形（形式檢查層）。

R01 與 R09 各依檢查層次拆成兩碼 —— `-1` 形式檢查層（可直接核對的文件、
程序、資料前置需求），`-2` 理解判斷層（需讀懂內容、理解語意後才能判斷）——
故本引擎共十一碼，與 §24 II 的九款為多對一，見 `engine.STATUTORY_CLAUSE`。

R01-2 / R02 / R06 / R09-2 本階段明示不檢查 ——
`screen()` 仍會回傳這四碼，判定為 NOT_COVERED。

用法（說明用，非 doctest —— 可執行的範例見 `try_case.py` 與 `tests/`）：

    from datetime import date
    from foi_screening import ApplicationFacts, PriorEvaluation, screen

    report = screen(ApplicationFacts(
        application_date=date(2024, 3, 1),
        has_complained=True,
        complaint_date=date(2024, 1, 1),
        business_replied=True,
        reply_received_date=date(2024, 1, 20),
        prior_evaluation=PriorEvaluation.NONE,
        proceedings=(),
    ))

`report.results` 恆為十一筆，順序同 `ALL_CODES`；未填的 `readiness` 與
`dispute_category` 會讓 R01-1、R09-1 回 INSUFFICIENT。
"""

from .engine import (
    ALL_CODES,
    NOT_COVERED_CODES,
    STATUTORY_CLAUSE,
    ScreeningReport,
    screen,
    screen_rule,
)
from .facts import (
    LISTED_CATEGORIES,
    ApplicationFacts,
    RuleFacts,
    ApplicationReadiness,
    DisputeCategory,
    PriorEvaluation,
    Proceeding,
    ProceedingKind,
    ProceedingStatus,
    SubmissionMethod,
)
from .params import DEFAULT_PARAMS, PROVENANCE, LegalParams
from .results import ICONS, RuleResult, Verdict

__all__ = [
    "ALL_CODES",
    "NOT_COVERED_CODES",
    "STATUTORY_CLAUSE",
    "ScreeningReport",
    "screen",
    "screen_rule",
    "ApplicationFacts",
    "RuleFacts",
    "ApplicationReadiness",
    "DisputeCategory",
    "LISTED_CATEGORIES",
    "SubmissionMethod",
    "PriorEvaluation",
    "Proceeding",
    "ProceedingKind",
    "ProceedingStatus",
    "DEFAULT_PARAMS",
    "PROVENANCE",
    "LegalParams",
    "ICONS",
    "RuleResult",
    "Verdict",
]
