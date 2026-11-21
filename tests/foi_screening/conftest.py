"""測試共用的填答建構器。

十一個測試檔原本各自複製一份 `ApplicationFacts` 的建構呼叫（連同同一組日期），
`ApplicationReadiness` 的「全部備妥」欄位表更是抄了四份。改一個欄位要改十一個
地方，正是上一輪新增 F17–F22 時最容易漏掉的地方。這裡收成一份：

    facts()           基準申請，不含 F17–F22（兩個新欄位維持 None＝沒填）
    readiness()       全部備妥的線上、本人、無代理人申請書
    complete_facts()  facts() 再補上 readiness() 與 F22，七碼全通過

三者都吃 `**overrides`，要測哪個分支就覆寫哪個欄位。
pytest 會把 `tests/` 放進 `sys.path`，測試檔直接 `from conftest import ...` 即可。
"""

from __future__ import annotations

from datetime import date

from foi_screening.facts import (
    ApplicationFacts,
    ApplicationReadiness,
    DisputeCategory,
    PriorEvaluation,
    SubmissionMethod,
)

#: 基準日期：2024-01-01 申訴、業者 2024-01-20 回覆（在三十日期限內）、
#: 2024-03-01 提出申請（在六十日期限內）—— R03／R04／R05 皆通過。
BASE_FACTS = dict(
    application_date=date(2024, 3, 1),
    has_complained=True,
    complaint_date=date(2024, 1, 1),
    complaint_received_date=date(2024, 1, 1),
    business_replied=True,
    reply_received_date=date(2024, 1, 20),
    business_reply_date=date(2024, 1, 20),
    prior_evaluation=PriorEvaluation.NONE,
    proceedings=(),
)

#: 一份線上送件、本人申請、無代理人、全部備妥的申請書。
#: 不適用的項目是 None 而非 False —— 線上送件不需繕本、無代理人不需委任狀，
#: 「不適用」與「該有卻沒有」在 R01-1 是兩回事。
COMPLETE_READINESS = dict(
    submission_method=SubmissionMethod.ONLINE,
    has_legal_representative=False,
    legal_rep_applying_alone=None,
    has_appointed_agent=False,
    respondent_count=None,
    has_application_form=True,
    has_claim_stated=True,
    has_facts_and_reasons=True,
    is_signed=True,
    has_id_copy=True,
    has_legal_rep_proof=None,
    has_other_party_consent=None,
    has_power_of_attorney=None,
    has_copies_for_respondents=None,
)


def readiness(**overrides) -> ApplicationReadiness:
    """全部備妥的申請書齊備情形；覆寫要測的欄位。"""
    return ApplicationReadiness(**{**COMPLETE_READINESS, **overrides})


def facts(**overrides) -> ApplicationFacts:
    """基準申請。`readiness` 與 `dispute_category` 維持 None，代表使用者沒填。"""
    return ApplicationFacts(**{**BASE_FACTS, **overrides})


def complete_facts(**overrides) -> ApplicationFacts:
    """七碼全通過的完整申請：基準申請再補上齊備的申請書與 F22。"""
    return facts(
        **{
            "readiness": readiness(),
            "dispute_category": DisputeCategory.NONE_OF_THESE,
            **overrides,
        }
    )
