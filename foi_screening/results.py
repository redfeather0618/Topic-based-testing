"""判定結果的型別。

大綱 §5.2 要求三值輸出（🔴 有障礙／🟢 無障礙／⚪ 無法判斷）。
實作時把 ⚪ 拆成三種，因為它們的補救動作完全不同：使用者補填欄位、
本工具根本不檢查、法律認定本身有爭議。對外仍可摺回三色呈現。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Verdict(Enum):
    """單一 R Code 的判定結果。"""

    BLOCKED = "有障礙"
    """🔴 規則命中，依法構成不受理事由。"""

    CLEAR = "無此障礙"
    """🟢 規則檢查通過。"""

    INSUFFICIENT = "資料不足"
    """⚪ 使用者沒填必要欄位，補填後即可判斷。"""

    NOT_COVERED = "本工具不檢查"
    """⚪ 此碼需語意判斷或外部清單，階段 A 不覆蓋。"""

    DISPUTED = "法律認定有爭議"
    """⚪ 不同的（都站得住腳的）認定會導出不同結論。"""


#: 呈現用的圖示。DISPUTED / INSUFFICIENT / NOT_COVERED 都摺回大綱 §5.2 的 ⚪。
ICONS = {
    Verdict.BLOCKED: "🔴",
    Verdict.CLEAR: "🟢",
    Verdict.INSUFFICIENT: "⚪",
    Verdict.NOT_COVERED: "⚪",
    Verdict.DISPUTED: "⚪",
}


@dataclass(frozen=True)
class RuleResult:
    """單一 R Code 的完整判定。"""

    code: str
    """如 "R05"。"""

    name: str
    """如 "申請已逾法定期限"。"""

    verdict: Verdict

    reason: str
    """面向使用者的說明。"""

    legal_basis: tuple[str, ...]
    """條文出處，供大綱 §6.0 第 1 項的條文對照審查使用。"""

    remedy: str | None = None
    """可執行的補救動作。BLOCKED 與 INSUFFICIENT 時必填。"""

    correctable: bool = False
    """§24 II 但書：本款情形是否屬「可以補正」者。"""

    self_declared: bool = False
    """是否純靠使用者自陳、評議中心以外無從查證（大綱 §5.1 對 R07/R08 的警語）。"""

    computed: dict[str, Any] = field(default_factory=dict)
    """算出來的中間值（起算日、期限日、剩餘天數等），供說明與除錯。"""

    @property
    def icon(self) -> str:
        return ICONS[self.verdict]
