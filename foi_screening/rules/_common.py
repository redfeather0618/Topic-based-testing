"""規則模組共用的結果建構。

七條規則在「使用者沒填必要欄位」時回的 INSUFFICIENT 形狀相同，各模組以
`functools.partial` 綁住自己的三個常數，呼叫端就只剩 reason 與 remedy：

    _insufficient = partial(insufficient, CODE, NAME, LEGAL_BASIS)
"""

from __future__ import annotations

from typing import Any

from ..results import RuleResult, Verdict


def insufficient(
    code: str,
    name: str,
    legal_basis: tuple[str, ...],
    reason: str,
    remedy: str,
    *,
    self_declared: bool = False,
    computed: dict[str, Any] | None = None,
) -> RuleResult:
    """建構一筆「資料不足」的判定。`remedy` 必填：要補什麼是本判定的重點。"""
    return RuleResult(
        code=code,
        name=name,
        verdict=Verdict.INSUFFICIENT,
        reason=reason,
        remedy=remedy,
        legal_basis=legal_basis,
        self_declared=self_declared,
        computed=computed or {},
    )
