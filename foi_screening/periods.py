"""期間計算。

民法 §120：「以時定期間者，即時起算。以日、星期、月或年定期間者，其始日不算入。」
民法 §122：「於一定期日或期間內，應為意思表示或給付者，其期日或其期間之末日，
            為星期日、紀念日或其他休息日時，以其休息日之次日代之。」

所有日期規則都必須經過這裡，不得各自用 timedelta 硬算。
"""

from __future__ import annotations

from datetime import date, timedelta

from .params import LegalParams

#: 星期六與星期日。機關週休二日，星期六實務上屬民法 §122 的「其他休息日」。
#: 國定假日需逐年維護的外部日曆表，本階段不引入 —— 見 docs/known_issues.md KI-01。
_WEEKEND = (5, 6)


def add_days(start: date, days: int, params: LegalParams) -> date:
    """從 `start` 起算 `days` 日，回傳期間的末日。

    依 `params.exclude_first_day`（民法 §120）決定始日是否算入，
    再依 `params.holiday_rollover`（民法 §122）決定末日是否順延。
    """
    if days <= 0:
        raise ValueError(f"期間天數必須為正整數，收到 {days}")

    offset = days if params.exclude_first_day else days - 1
    end = start + timedelta(days=offset)

    if params.holiday_rollover:
        # 只處理週末。國定假日需要外部日曆表，本階段不引入（KI-01），
        # 改以 r05／engine 的 remedy 文案提醒使用者。
        while end.weekday() in _WEEKEND:
            end += timedelta(days=1)

    return end


def is_expired(application_date: date, deadline: date) -> bool:
    """申請日是否已逾期限末日。末日當天提出仍屬期限內。"""
    return application_date > deadline
