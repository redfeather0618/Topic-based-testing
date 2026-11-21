"""R09-1 其他主管機關規定之情形 —— 形式檢查層。

金保法 §24 II 九：「其他主管機關規定之情形。」

該「主管機關規定」即評議程序辦法 §15 I 九（該辦法 §1 明載授權依據
包含金保法 §24 II 九）：

> 九、申請評議事件純屬債務協商、投資表現、信用評等或定價政策之範圍者。

§15 II 另定義「定價政策」的範圍（見 `docs/legal_basis.md` §一）。

**本層只確認類別落不落在清單內。** 限定詞「純屬」需讀懂爭議內容才能認定，
已整個歸給 R09-2（階段 B），故本規則永遠不會輸出 BLOCKED。
"""

from __future__ import annotations

from functools import partial

from ..facts import LISTED_CATEGORIES, ApplicationFacts
from ..params import LegalParams
from ..results import RuleResult, Verdict
from ._common import insufficient

CODE = "R09-1"
NAME = "其他主管機關規定之情形 —— 形式檢查層"
LEGAL_BASIS = ("金保法§24 II 九", "評議程序辦法§15 I 九", "評議程序辦法§15 II")

#: 爭議類別由使用者自陳，本工具無從查證。
_insufficient = partial(insufficient, CODE, NAME, LEGAL_BASIS, self_declared=True)


def check(facts: ApplicationFacts, params: LegalParams) -> RuleResult:
    category = facts.dispute_category

    if category is None:
        return _insufficient(
            "你尚未填答爭議標的屬於哪一類，無法判斷此項。",
            (
                "請填寫 F22「爭議標的類別」：債務協商、投資表現、信用評等、"
                "定價政策，或以上皆非。"
            ),
            # 呈現層會讀 computed["listed"]，未填答時也得有鍵，不能 KeyError
            computed={"listed": None, "category": None},
        )

    if category not in LISTED_CATEGORIES:
        return RuleResult(
            code=CODE,
            name=NAME,
            verdict=Verdict.CLEAR,
            reason=(
                "依你的填答，爭議標的不屬於債務協商、投資表現、信用評等或定價政策，"
                "不在評議程序辦法 §15 I 九的列舉範圍內。"
            ),
            legal_basis=LEGAL_BASIS,
            self_declared=True,
            computed={"listed": False, "category": category.value},
        )

    return RuleResult(
        code=CODE,
        name=NAME,
        verdict=Verdict.CLEAR,
        reason=(
            f"依你的填答，爭議標的為「{category.value}」，已落入評議程序辦法 "
            "§15 I 九的列舉範圍。但本款須爭議「純屬」該範圍才成立 —— "
            "若你的爭議同時涉及其他爭點（例如業者說明義務、作業疏失、契約條款解釋），"
            "通常不因此不受理。是否「純屬」屬 R09-2 理解判斷層，本工具不檢查。"
        ),
        legal_basis=LEGAL_BASIS,
        self_declared=True,
        computed={"listed": True, "category": category.value},
    )
