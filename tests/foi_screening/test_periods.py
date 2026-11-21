"""期間計算 —— 民法 §120（始日不算入）、§122（末日休息日順延）。

這是其他所有日期規則的地基，先單獨驗證。
"""

from datetime import date

import pytest

from foi_screening.params import DEFAULT_PARAMS, LegalParams
from foi_screening.periods import add_days, is_expired


def test_始日不算入_申訴日加三十日為次月同日前一天():
    """民法§120：1/1 申訴，三十日期限屆滿日為 1/31，不是 1/30。"""
    assert add_days(date(2024, 1, 1), 30, DEFAULT_PARAMS) == date(2024, 1, 31)


def test_始日不算入_可關閉():
    """exclude_first_day=False 時改為把始日算入，末日提前一天。"""
    params = DEFAULT_PARAMS.replace(exclude_first_day=False)
    assert add_days(date(2024, 1, 1), 30, params) == date(2024, 1, 30)


def test_跨閏年_二月二十九日被計入():
    """2024 是閏年：1/31 起算三十日，末日為 3/1（2/29 佔掉一天）。"""
    assert add_days(date(2024, 1, 31), 30, DEFAULT_PARAMS) == date(2024, 3, 1)


def test_跨平年_二月只有二十八天():
    """2023 非閏年：同樣的 1/31 起算三十日，末日為 3/2。"""
    assert add_days(date(2023, 1, 31), 30, DEFAULT_PARAMS) == date(2023, 3, 2)


def test_六十日期間跨年():
    assert add_days(date(2024, 12, 1), 60, DEFAULT_PARAMS) == date(2025, 1, 30)


def test_末日為週日_預設不順延():
    """holiday_rollover 預設關閉（民法§122 是否適用評議程序未經查證）。"""
    # 2024-03-03 是星期日
    assert add_days(date(2024, 2, 2), 30, DEFAULT_PARAMS) == date(2024, 3, 3)
    assert date(2024, 3, 3).weekday() == 6


def test_末日為週日_開啟順延時移到週一():
    """民法§122：末日為星期日者，以其次日代之。"""
    params = DEFAULT_PARAMS.replace(holiday_rollover=True)
    assert add_days(date(2024, 2, 2), 30, params) == date(2024, 3, 4)


def test_末日為週六_開啟順延時移到週一():
    """機關週休二日，星期六屬民法§122 的「其他休息日」。

    2024-03-02 是星期六，連同次日星期日一起跳過，末日為 03-04 星期一。
    """
    params = DEFAULT_PARAMS.replace(holiday_rollover=True)
    assert date(2024, 3, 2).weekday() == 5
    assert add_days(date(2024, 2, 1), 30, params) == date(2024, 3, 4)


def test_末日為週六_預設仍不順延():
    """預設採較嚴格的認定（期限較早）。

    放寬不在這一層做 —— 邊緣案例由 engine 的敏感度分析降級為 DISPUTED。
    """
    assert add_days(date(2024, 2, 1), 30, DEFAULT_PARAMS) == date(2024, 3, 2)


def test_國定假日不在順延範圍內():
    """已知限制 KI-01：只處理週末，不含國定假日。

    2024-02-28 是和平紀念日（星期三），順延與否都停在這天 ——
    這個缺口改以 r05／engine 的 remedy 文案提醒使用者，不在此處補。
    """
    params = DEFAULT_PARAMS.replace(holiday_rollover=True)
    assert add_days(date(2024, 1, 29), 30, params) == date(2024, 2, 28)


def test_申請日等於期限末日_未逾期():
    assert is_expired(date(2024, 3, 1), deadline=date(2024, 3, 1)) is False


def test_申請日晚於期限末日一天_逾期():
    assert is_expired(date(2024, 3, 2), deadline=date(2024, 3, 1)) is True


def test_申請日早於期限末日_未逾期():
    assert is_expired(date(2024, 1, 1), deadline=date(2024, 3, 1)) is False


def test_replace_不改動原參數物件():
    """LegalParams 必須是不可變的，replace 回傳新物件。"""
    original = DEFAULT_PARAMS
    changed = original.replace(holiday_rollover=True)
    assert original.holiday_rollover is False
    assert changed.holiday_rollover is True
    assert isinstance(changed, LegalParams)


def test_天數必須為正():
    with pytest.raises(ValueError):
        add_days(date(2024, 1, 1), 0, DEFAULT_PARAMS)
