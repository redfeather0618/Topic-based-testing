"""使用者填答的事實 —— 規則引擎的唯一輸入。

只收階段 A 七碼真正需要的欄位。對應大綱 §3.2 表單的 F07–F12 與 F17–F22。

⚠️ 「爭議事件發生日」與「知悉爭議之日」不在此處，也不該被加回來。
   §13 II 的六十日自「收受處理結果」或「三十日期限屆滿」起算，與爭議何時
   發生、何時知悉無關，金保法亦無以爭議發生日為起點的申請期限。原列為大綱
   §3.2 的 F05／F06，已於 2026-09-21 刪除。這是本檔的正本說明，其餘各處指向這裡。

任何欄位為 `None` 一律代表「使用者沒填」，不得當成 False 或空值。
判定必要事實未知時回傳 INSUFFICIENT；若其他已知事實足以確定該規則結果，
可據其判斷，例如 R05 有一條明確未屆滿的有效期限即可排除逾期。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum


class PriorEvaluation(Enum):
    """F11 截至本次提出時是否曾就同一事件申請過評議、結果為何。"""

    NONE = "未曾申請過評議"
    PENDING = "曾申請，尚無結果"
    ACCEPTED = "曾申請且評議成立"
    REJECTED = "曾申請且評議不成立"
    WITHDRAWN = "曾申請後撤回"


class SubmissionMethod(Enum):
    """F17 送件方式。決定繕本項目是否適用。"""

    PAPER = "紙本（郵寄或臨櫃）"
    ONLINE = "線上申請"


class DisputeCategory(Enum):
    """F22 爭議標的類別。前四項取自評議程序辦法 §15 I 九。"""

    DEBT_NEGOTIATION = "債務協商"
    INVESTMENT_PERFORMANCE = "投資表現"
    CREDIT_RATING = "信用評等"
    PRICING_POLICY = "定價政策"
    NONE_OF_THESE = "以上皆非"


#: 落入評議程序辦法 §15 I 九列舉範圍的類別。
LISTED_CATEGORIES = frozenset(
    {
        DisputeCategory.DEBT_NEGOTIATION,
        DisputeCategory.INVESTMENT_PERFORMANCE,
        DisputeCategory.CREDIT_RATING,
        DisputeCategory.PRICING_POLICY,
    }
)


class ProceedingKind(Enum):
    """F12 曾進行的其他爭議處理程序種類。

    種類取自金保法 §24 II 八所列：法院判決、調處、評議、和解、調解、仲裁。
    """

    COURT_JUDGMENT = "法院判決"
    MEDIATION_FOI = "調處"
    EVALUATION = "評議"
    SETTLEMENT = "和解"
    MEDIATION_OTHER = "調解"
    ARBITRATION = "仲裁"


class ProceedingStatus(Enum):
    """該程序目前的狀態。成立與不成立的法律效果完全相反：

      CONCLUDED → §24 II 八，不受理
      FAILED    → 不觸發 §24 II 八；若為調處或調解，反而依 §23 V
                  取得「自不成立之日起六十日」的申請視窗
    """

    PENDING = "進行中／判決尚未確定"
    CONCLUDED = "已成立／判決已確定"
    FAILED = "不成立"


#: §23 V 只給「依其他法律規定調處或調解不成立」者新的申請視窗，
#: 和解、仲裁、評議、法院判決不在其列。
MEDIATION_KINDS = frozenset({ProceedingKind.MEDIATION_FOI, ProceedingKind.MEDIATION_OTHER})


@dataclass(frozen=True)
class Proceeding:
    """一項已進行或已結束的爭議處理程序。"""

    kind: ProceedingKind
    status: ProceedingStatus
    date: date | None = None
    """成立或不成立之日。§23 V 的六十日起算需要；PENDING 時通常為 None。"""

    covers_current_case: bool | None = None
    """人工確認該程序涵蓋本 Case；False 為其他事件，None 為未確認。"""


@dataclass(frozen=True)
class ApplicationReadiness:
    """F17–F21 —— 申請書的記載事項與應附文件是否齊備。

    只涵蓋評議程序辦法 §13 五項載明事項中的「請求標的」與「事實、理由」，
    以及應檢具的文件；當事人名稱及基本資料、申訴未獲妥適處理之情形等
    其餘載明事項尚未納入本層檢查。
    任一欄位為 None 代表使用者沒填，R01-1 會回 INSUFFICIENT 並列出待辦。
    """

    # —— 情境題：決定哪些項目適用 ——
    submission_method: SubmissionMethod | None
    """F17 送件方式。"""

    has_legal_representative: bool | None
    """F18 是否有法定代理人。"""

    legal_rep_applying_alone: bool | None
    """F18a 法定代理人是否單方面申請。只在 F18 為 True 時需填。"""

    has_appointed_agent: bool | None
    """F19 是否有委任代理人。"""

    respondent_count: int | None
    """F20 相對人人數。只在紙本送件時需填，供計算繕本份數；
    本身不是判定項目，不會出現在缺件清單。"""

    # —— 一律必備 ——
    has_application_form: bool | None
    has_claim_stated: bool | None
    has_facts_and_reasons: bool | None
    is_signed: bool | None
    has_id_copy: bool | None

    # —— 條件必備 ——
    has_legal_rep_proof: bool | None
    """法定代理人證明文件。僅 has_legal_representative is True 時適用。"""

    has_other_party_consent: bool | None
    """他方同意書。僅 legal_rep_applying_alone is True 時適用。"""

    has_power_of_attorney: bool | None
    """委任狀。僅 has_appointed_agent is True 時適用。"""

    has_copies_for_respondents: bool | None
    """按相對人人數提出的繕本及證據資料。僅紙本送件時適用。"""


@dataclass(frozen=True)
class ApplicationFacts:
    """使用者在申請評議前能自行提供的全部事實。"""

    application_date: date
    """F10 預計提出評議申請日（預設為今天）。"""

    has_complained: bool | None
    """F07 截至 application_date 是否已就本 Case 向正確相對金融服務業有效申訴。
    不可僅因一般理賠往來或其他事件申訴填 True；未知有效性應填 None。

    依 §13 II 後段，向爭議處理機構提出申訴、經其移交金融服務業處理者，
    同樣算已申訴，此處應填 True。
    """

    complaint_date: date | None
    """F08 申訴提出日。"""

    business_replied: bool | None
    """F09 業者是否已回覆本 Case 的申訴處理結果。
    R04 觀察 application_date；R05 已知中心收文日時觀察該日。
    R05 以中心收文前已明示的回覆日期事件優先於較早時點的 bool。
    無日期可核對時須按該碼觀察點確認 bool，未知填 None。"""

    reply_received_date: date | None
    """F09 收受處理結果之日。"""

    prior_evaluation: PriorEvaluation | None
    """F11 曾否依本法申請評議及其結果。"""

    proceedings: tuple[Proceeding, ...] | None
    """F12 其他爭議處理程序。空 tuple 代表「都沒有」，None 代表「沒填」。"""

    readiness: ApplicationReadiness | None = None
    """F17–F21 申請書齊備情形。R01-1 使用。"""

    dispute_category: DisputeCategory | None = None
    """F22 爭議標的類別。R09-1 使用。"""

    complaint_received_date: date | None = None
    """業者實際收受申訴日；不得用申訴提出日代填。"""

    business_reply_date: date | None = None
    """業者實際回覆處理結果日；與申請人收受處理結果日分開。"""

    center_received_date: date | None = None
    """中心實際收文日；R05 優先作比較終點，不覆寫 application_date（提出日）。"""


@dataclass(frozen=True)
class RuleFacts:
    """五碼逐規則回放的部分事實。不補造 ApplicationFacts 所需的申請日期。"""

    application_date: date | None = None
    has_complained: bool | None = None
    complaint_date: date | None = None
    business_replied: bool | None = None
    reply_received_date: date | None = None
    prior_evaluation: PriorEvaluation | None = None
    proceedings: tuple[Proceeding, ...] | None = None

    complaint_received_date: date | None = None
    """業者實際收受申訴日；不得用申訴提出日代填。"""

    business_reply_date: date | None = None
    """業者實際回覆處理結果日；與申請人收受處理結果日分開。"""

    center_received_date: date | None = None
    """中心實際收文日；R05 優先作比較終點，不覆寫 application_date（提出日）。"""
