"""規則引擎 —— 把七條規則跑完，並誠實交代沒跑的那四條。

大綱 §4.3 的前提：「階段 A 只覆蓋 11 碼中的 7 碼，所以它絕不能輸出『你沒有問題』，
只能輸出『在可自動檢查的項目中沒有問題，另有 N 項需人工判斷』。」

這個前提在這裡是用結構守住的，不是靠寫文案時自律：
  1. `screen()` 永遠回傳十一筆結果，未覆蓋的四碼明示為 NOT_COVERED
  2. `ScreeningReport.summary_text` 由模板產生，模板裡沒有「通過即可送件」這種語句
  3. 日期規則會跑敏感度分析，兩種認定結論不同時降級為 DISPUTED
"""

from __future__ import annotations

from dataclasses import dataclass

from .facts import ApplicationFacts, RuleFacts
from .params import DEFAULT_PARAMS, LegalParams
from .results import RuleResult, Verdict
from .rules import r01_1, r03, r04, r05, r07, r08, r09_1

#: 本引擎的碼。R01 與 R09 各依檢查層次拆成兩碼：
#:   -1 形式檢查層 —— 可直接核對的文件、程序、資料前置需求
#:   -2 理解判斷層 —— 需讀懂內容、理解語意後才能判斷
#: 因此碼與 §24 II 的九款是「多對一」而非一一對應 —— 拆分是本專案的分析，
#: 不是法條的結構。`STATUTORY_CLAUSE` 記錄每一碼回到哪一款。
ALL_CODES = (
    "R01-1",
    "R01-2",
    "R02",
    "R03",
    "R04",
    "R05",
    "R06",
    "R07",
    "R08",
    "R09-1",
    "R09-2",
)

#: 每一碼對應的 §24 II 款次。多碼可指向同一款。
STATUTORY_CLAUSE = {
    "R01-1": 1,
    "R01-2": 1,
    "R02": 2,
    "R03": 3,
    "R04": 4,
    "R05": 5,
    "R06": 6,
    "R07": 7,
    "R08": 8,
    "R09-1": 9,
    "R09-2": 9,
}

#: 階段 A 實作的規則模組，依 R Code 索引。
COVERED = {
    "R01-1": r01_1,
    "R03": r03,
    "R04": r04,
    "R05": r05,
    "R07": r07,
    "R08": r08,
    "R09-1": r09_1,
}

#: 未覆蓋碼的通用補救 —— 本工具不判斷，也沒有條文可據以指出補救方向。
_GENERIC_REMEDY = "請自行評估，或洽詢評議中心、律師等專業人士。"


@dataclass(frozen=True)
class _NotCoveredSpec:
    """一個未覆蓋碼的固定文案。

    `remedy` 與 `correctable` 之所以可逐碼指定，是因為「本工具不檢查」
    不等於「無話可說」：R01 兩碼依 §24 II 但書明文可以補正，
    即使引擎不判斷，也該把這件事告訴使用者，而不是給通用文案。
    """

    name: str
    legal_basis: tuple[str, ...]
    why: str
    remedy: str = _GENERIC_REMEDY
    correctable: bool = False


_NOT_COVERED_SPEC = {
    "R01-2": _NotCoveredSpec(
        name="申請不合程式 —— 理解判斷層",
        legal_basis=("金保法§24 II 一", "評議程序辦法§13"),
        why=(
            "請求標的是否明確可執行、事實與理由是否足以支撐請求，需讀懂內容做實質判斷"
            "（規劃於階段 B）"
        ),
        remedy=(
            "請確認請求標的寫出具體請求（例如請求給付的金額及其計算方式），"
            "且事實與理由足以支撐該請求。本工具無法判斷你寫得夠不夠，"
            "但本款依 §24 II 但書可以補正。"
        ),
        correctable=True,
    ),
    "R02": _NotCoveredSpec(
        name="非屬金融消費爭議",
        legal_basis=("金保法§24 II 二",),
        why="是否屬金融消費者與金融服務業間的金融消費爭議，需判斷爭議性質",
    ),
    "R06": _NotCoveredSpec(
        name="當事人不適格",
        legal_basis=("金保法§24 II 六",),
        why="申請人與相對人的資格，需判斷契約關係與當事人身分",
    ),
    "R09-2": _NotCoveredSpec(
        name="其他主管機關規定之情形 —— 理解判斷層",
        legal_basis=("金保法§24 II 九", "評議程序辦法§15 I 九"),
        why=(
            "條文限於「純屬」該四類之範圍，爭議是否純屬其中，需讀懂爭議內容後認定"
            "（規劃於階段 B）"
        ),
        remedy=(
            "條文的限定詞是「純屬」—— 爭議若同時涉及該四類以外的爭點（例如業者說明義務、"
            "作業疏失、契約條款解釋），通常不因此不受理。本工具無法替你認定，"
            "請自行評估或洽詢評議中心。"
        ),
    ),
}

#: 本階段明示不檢查的碼，全部需讀懂內容或判斷爭議性質。
#: 由 `_NOT_COVERED_SPEC` 推導，不另列一份清單。
NOT_COVERED_CODES = tuple(_NOT_COVERED_SPEC)

#: 只對日期規則做敏感度分析 —— 非日期規則的判斷不涉及期間認定。
_DATE_SENSITIVE_CODES = ("R04", "R05")


def _alternative_params(params: LegalParams) -> dict[str, LegalParams]:
    """其他同樣站得住腳的法律認定。

    只列「預設值本身就是判斷、且該判斷尚未確認」的參數；`exclude_first_day`
    （民法 §120 明文）與業者逾期後才回覆的起算點（已確認）都不在其中。
    詳見 `docs/legal_basis.md` §四、`docs/known_issues.md` KI-01。
    """
    return {
        "期間末日為休息日時依民法 §122 順延": params.replace(holiday_rollover=True),
    }


def _with_sensitivity(
    code: str, primary: RuleResult, facts: ApplicationFacts | RuleFacts, params: LegalParams
) -> RuleResult:
    """若換一種認定會得出不同結論，就把結果降級為 DISPUTED。"""
    if code not in _DATE_SENSITIVE_CODES:
        return primary
    if primary.verdict in (Verdict.INSUFFICIENT, Verdict.NOT_COVERED):
        return primary

    module = COVERED[code]
    disagreements = {}
    for label, alt in _alternative_params(params).items():
        verdict = module.check(facts, alt).verdict
        if verdict is not primary.verdict:
            disagreements[label] = verdict

    if not disagreements:
        return primary

    detail = "；".join(
        f"若「{label}」，本項為「{verdict.value}」" for label, verdict in disagreements.items()
    )
    return RuleResult(
        code=primary.code,
        name=primary.name,
        verdict=Verdict.DISPUTED,
        reason=(
            f"這一項的結論會隨法律認定而改變。依本工具的預設認定為「{primary.verdict.value}」；"
            f"{detail}。這些認定條文均無明文，本工具無法替你決定。"
            f"（預設認定的理由：{primary.reason}）"
        ),
        remedy=(
            "請把本項視為有風險，儘早送件，並保留所有日期的書面證明。"
            "另外，本工具的期限計算只把星期六與星期日當作休息日，不含國定假日；"
            "若末日前後有春節、清明等連假，依民法 §122 真正的末日可能比這裡顯示的更晚。"
            "這是對你有利的方向，但不要因此拖延。最終認定以評議中心為準。"
        ),
        correctable=primary.correctable,
        self_declared=primary.self_declared,
        legal_basis=primary.legal_basis,
        computed={**primary.computed, "alternatives": disagreements},
    )


def _not_covered(code: str) -> RuleResult:
    spec = _NOT_COVERED_SPEC[code]
    return RuleResult(
        code=code,
        name=spec.name,
        verdict=Verdict.NOT_COVERED,
        reason=f"本工具無法檢查這一項：{spec.why}。",
        remedy=spec.remedy,
        correctable=spec.correctable,
        legal_basis=spec.legal_basis,
    )


@dataclass(frozen=True)
class ScreeningReport:
    """一次審查的完整結果。永遠涵蓋 `ALL_CODES` 的全部十一碼。"""

    results: tuple[RuleResult, ...]
    params: LegalParams

    def by_code(self, code: str) -> RuleResult:
        for result in self.results:
            if result.code == code:
                return result
        raise KeyError(f"未知的不受理事由代碼：{code}")

    def _of(self, verdict: Verdict) -> tuple[RuleResult, ...]:
        return tuple(r for r in self.results if r.verdict is verdict)

    @property
    def blocked(self) -> tuple[RuleResult, ...]:
        """🔴 明確有障礙。"""
        return self._of(Verdict.BLOCKED)

    @property
    def cleared(self) -> tuple[RuleResult, ...]:
        """🟢 明確無此障礙。"""
        return self._of(Verdict.CLEAR)

    @property
    def needs_input(self) -> tuple[RuleResult, ...]:
        """⚪ 使用者補填欄位後即可判斷。"""
        return self._of(Verdict.INSUFFICIENT)

    @property
    def disputed(self) -> tuple[RuleResult, ...]:
        """⚪ 法律認定本身有爭議。"""
        return self._of(Verdict.DISPUTED)

    @property
    def not_covered(self) -> tuple[RuleResult, ...]:
        """⚪ 本工具不檢查。"""
        return self._of(Verdict.NOT_COVERED)

    @property
    def summary_text(self) -> str:
        """總結文案。

        模板刻意不提供「通過即可送件」這類語句 —— 大綱 §7：
        絕不能讓使用者以為通過檢查就等於會被受理。
        """
        uncovered = "、".join(f"{r.code} {r.name}" for r in self.not_covered)
        return (
            f"可自動檢查的 {len(COVERED)} 項程序條件中："
            f"通過 {len(self.cleared)} 項、"
            f"有明確障礙 {len(self.blocked)} 項、"
            f"資料不足 {len(self.needs_input)} 項、"
            f"法律認定有爭議 {len(self.disputed)} 項。\n"
            f"另有 {len(self.not_covered)} 項本工具無法檢查，需由人工判斷：{uncovered}。\n"
            "本工具不構成法律意見，實際受理與否以金融消費評議中心的決定為準。"
        )


REPLAY_CODES = ("R03", "R04", "R05", "R07", "R08")


def screen_rule(
    code: str, facts: ApplicationFacts | RuleFacts, params: LegalParams = DEFAULT_PARAMS
) -> RuleResult:
    """只執行已啟用的一碼；與完整引擎共用規則和敏感度分析。"""
    if code not in REPLAY_CODES:
        raise ValueError(f"逐規則入口尚未啟用 {code}")
    module = COVERED[code]
    errors = []
    observation_date = (
        facts.center_received_date or facts.application_date
        if code == "R05" else facts.application_date
    )
    if code in ("R03", "R04", "R05"):
        complaint, reply, application = facts.complaint_date, facts.reply_received_date, observation_date
        if code != "R03" and complaint and reply and reply < complaint:
            errors.append("收受回覆日期早於同一申訴提出日期")
        if complaint and application and complaint > application:
            errors.append("申訴日期晚於本次申請觀察時點")
        if code != "R03" and reply and application and reply > application:
            errors.append("收受回覆日期晚於本次申請觀察時點")
        if code in _DATE_SENSITIVE_CODES:
            receipt, sent = facts.complaint_received_date, facts.business_reply_date
            for earlier, later, message in (
                (complaint, receipt, "業者收受申訴早於申訴提出"),
                (receipt, sent, "業者回覆早於收受申訴"),
                (sent, reply, "申請人收受處理結果早於業者回覆"),
                (facts.application_date, facts.center_received_date, "中心收文早於評議提出"),
            ):
                if earlier and later and later < earlier:
                    errors.append(message)
            if application and any(d and d > application for d in (receipt, sent)):
                errors.append("申訴收受或業者回覆晚於本次申請觀察時點")
    if code in ("R05", "R08") and observation_date and facts.proceedings:
        if any(p.date and p.date > observation_date
               and p.covers_current_case is not False for p in facts.proceedings):
            errors.append("既有程序日期晚於本次申請觀察時點")
    if errors:
        return RuleResult(code=code, name=module.NAME, verdict=Verdict.INSUFFICIENT,
            reason="輸入日期互相矛盾，未執行期間判定。", remedy="請核對日期事件與觀察時點。",
            legal_basis=module.LEGAL_BASIS, computed={"input_errors": errors})
    primary = module.check(facts, params)
    return _with_sensitivity(code, primary, facts, params)


def screen(
    facts: ApplicationFacts, params: LegalParams = DEFAULT_PARAMS
) -> ScreeningReport:
    """對一份申請跑完階段 A 的全部檢查。"""
    results = []
    for code in ALL_CODES:
        if code in REPLAY_CODES:
            results.append(screen_rule(code, facts, params))
        elif code in COVERED:
            primary = COVERED[code].check(facts, params)
            results.append(_with_sensitivity(code, primary, facts, params))
        else:
            results.append(_not_covered(code))
    return ScreeningReport(results=tuple(results), params=params)
