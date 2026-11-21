"""Read sealed connector snapshots without modifying the source."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re

MAIN_SHEET = '01_Case_Screening'
DETAIL_SHEETS = {
    'R03': '03_R03_未先向金融服務業申訴',
    'R04': '04_R04_申訴處理未逾30日',
    'R05': '05_R05_申請已逾法定期限',
    'R07': '06_R07_曾申請評議而不成立',
    'R08': '07_R08_已有確定或成立程序',
}
# 細表移除流水號後仍接受舊快照；只映射已知名稱，不猜測任意R碼。
SHEET_TITLE_ALIASES = {title[3:]: title for title in DETAIL_SHEETS.values()}


def snapshot_tables(snapshot: dict) -> dict[str, list[SourceRow]]:
    """以相容鍵尋找細表，但證據引用保留來源真正的工作表名稱。"""
    tables = {}
    for sheet in snapshot['sheets']:
        key = SHEET_TITLE_ALIASES.get(sheet['title'], sheet['title'])
        # 完整快照保留所有工作表；回放只解析主表與已核定五碼細表。
        if key not in {MAIN_SHEET, *DETAIL_SHEETS.values()}:
            continue
        if key in tables:
            raise ValueError(f'工作表重複對應：{key}')
        tables[key] = read_table(sheet)
    return tables


DEFERRED_CODES = ('R01', 'R02', 'R06', 'R09')
ALL_CODES = tuple(f'R{i:02}' for i in range(1, 10))


@dataclass(frozen=True)
class SourceRow:
    title: str
    row_number: int
    data: dict
    columns: dict[str, int]

    def reference(self, field: str) -> dict:
        return {'sheet': self.title, 'row': self.row_number,
                'column': self.columns.get(field), 'field': field}


def normalize_case_id(value: object) -> str:
    """Normalize only whitespace and a lower-case C suffix; never guess a key."""
    text = str(value or '').strip()
    if not re.fullmatch(r'\d+-\d+-[Cc][1-9]\d*', text):
        raise ValueError(f'Invalid case_id: {text!r}')
    return re.sub(r'-c(?=\d+$)', '-C', text)


def load_snapshot(path: str | Path) -> dict:
    path = Path(path)
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    expected = path.with_suffix('.sha256').read_text(encoding='ascii').strip()
    if digest != expected:
        raise ValueError('Snapshot SHA-256 mismatch')
    result = json.loads(raw.decode('utf-8'))
    if result.get('schema_version') != 1 or not isinstance(result.get('sheets'), list):
        raise ValueError('Unsupported snapshot schema')
    titles = [sheet['title'] for sheet in result['sheets']]
    if len(set(titles)) != len(titles):
        raise ValueError('Duplicate sheet titles')
    result['_sha256'] = digest
    return result


def read_table(sheet: dict) -> list[SourceRow]:
    values = sheet.get('values') or []
    if not values:
        return []
    headers = [str(v or '').split('\n')[0].strip() for v in values[0]]
    nonempty = [v for v in headers if v]
    if len(nonempty) != len(set(nonempty)):
        raise ValueError(f'Duplicate header in {sheet["title"]}')
    columns = {key: i+1 for i, key in enumerate(headers) if key}
    rows = []
    for number, raw in enumerate(values[1:], 2):
        if not any(v is not None and str(v).strip() for v in raw):
            continue
        data = {key: raw[i] if i < len(raw) else None for i, key in enumerate(headers) if key}
        rows.append(SourceRow(sheet['title'], number, data, columns))
    return rows
