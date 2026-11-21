"""法規參數 —— 每個數字與每個認定都在這裡，不寫死在規則邏輯中。

大綱 §5.3 明文要求：「實作時應把每個起算點的認定方式寫成顯式且可調整的參數，
而非硬寫在程式邏輯裡，以便日後取得驗證資料時能快速修正。」

`PROVENANCE` 記錄每個參數的條文出處與查證狀態。`verified=False` 的項目
是依條文文義所做的認定，未經評議中心實際案例驗證，必須寫進報告的已知限制。
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass


@dataclass(frozen=True)
class ParamProvenance:
    """一個法規參數的出處與查證狀態。"""

    source: str
    verified: bool
    note: str = ""


@dataclass(frozen=True)
class LegalParams:
    """規則引擎使用的全部法規認定。不可變；用 `replace()` 產生變體。"""

    # —— 條文明文的數字 ——
    business_processing_days: int = 30
    """金融服務業處理申訴的法定期間。"""

    filing_window_days: int = 60
    """自收受處理結果或期限屆滿之日起，得申請評議的期間。"""

    mediation_failure_window_days: int = 60
    """依其他法律調處／調解不成立後，得申請評議的期間。"""

    # —— 條文未明文、需要認定的部分 ——
    receipt_date_basis: str = "user_reported"
    """「收受處理結果之日」如何認定。目前直接採信使用者填答的日期。

    其他可能：郵戳日、到達日、實際閱讀日。條文未明文。
    """

    exclude_first_day: bool = True
    """民法 §120：以日定期間者，其始日不算入。"""

    holiday_rollover: bool = False
    """民法 §122：期間末日為休息日者順延。

    預設 False —— 採較嚴格的認定（期限較早），邊緣案例交由
    `engine._with_sensitivity()` 降級為 DISPUTED，而非在此放寬。
    開啟時處理星期六與星期日；國定假日需外部日曆表，本階段不引入。
    """

    def replace(self, **changes: object) -> "LegalParams":
        """回傳套用 `changes` 後的新參數物件；原物件不變。"""
        return dataclasses.replace(self, **changes)  # type: ignore[arg-type]


DEFAULT_PARAMS = LegalParams()


PROVENANCE: dict[str, ParamProvenance] = {
    "business_processing_days": ParamProvenance(
        source="金融消費者保護法 §13 II",
        verified=True,
        note="「金融服務業應於收受申訴之日起三十日內為適當之處理」。",
    ),
    "filing_window_days": ParamProvenance(
        source="金融消費者保護法 §13 II",
        verified=True,
        note="「得於收受處理結果或期限屆滿之日起六十日內，向爭議處理機構申請評議」。",
    ),
    "mediation_failure_window_days": ParamProvenance(
        source="金融消費者保護法 §23 V",
        verified=True,
        note="「已依其他法律規定調處或調解不成立者，得於調處或調解不成立之日起六十日內申請評議」。",
    ),
    "receipt_date_basis": ParamProvenance(
        source="條文無明文",
        verified=False,
        note="「收受處理結果之日」以郵戳、到達或閱讀為準，條文未定。目前採信使用者填答。",
    ),
    "exclude_first_day": ParamProvenance(
        source="民法 §120",
        verified=True,
        note="條文本身已核對；但民法期間規定是否確實適用於評議申請期間，未經查證。",
    ),
    "holiday_rollover": ParamProvenance(
        source="民法 §122",
        verified=False,
        note=(
            "條文本身已核對，但是否適用於評議程序未經查證，且完整實作需國定假日表。"
            "目前開啟時處理星期六與星期日，不含國定假日。"
        ),
    ),
}
