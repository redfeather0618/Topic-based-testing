"""Join annotation facts to the five-rule engine; keep labels outside mappings."""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import date, datetime, timezone
from enum import Enum
import hashlib
import json
from pathlib import Path
import re
import subprocess

from ..engine import screen_rule
from ..params import DEFAULT_PARAMS
from .mapping import MAPPING_VERSION, map_row
from .source import ALL_CODES, DEFERRED_CODES, DETAIL_SHEETS, MAIN_SHEET, load_snapshot, normalize_case_id, snapshot_tables


def _json_default(value):
    if isinstance(value, Enum):
        return value.name
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    raise TypeError(type(value).__name__)


def _json(value):
    return json.dumps(value, ensure_ascii=False, default=_json_default, sort_keys=True)


def _reviewed(row):
    return row is not None and all(str(row.data.get(k) or '').strip() == '已完成' for k in ('標註狀態', '檢核狀態'))


def _source_version():
    root = Path(__file__).resolve().parents[3]
    digest = hashlib.sha256()
    for path in sorted((root/'src').rglob('*.py')):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(path.read_bytes())
    def git(*args):
        try:
            result = subprocess.run(['git', *args], cwd=root, capture_output=True, check=True)
            return result.stdout.decode('utf-8').strip()
        except (OSError, subprocess.CalledProcessError):
            return 'unavailable'
    return {'commit': git('rev-parse', 'HEAD'), 'dirty': bool(git('status', '--porcelain')),
            'source_tree_sha256': digest.hexdigest()}


def run(snapshot_path: str | Path, output_dir: str | Path) -> dict:
    """Replay an immutable snapshot into a NEW directory; no network or source writes."""
    output = Path(output_dir)
    if output.exists():
        raise FileExistsError(f'Output already exists: {output}')
    snapshot = load_snapshot(snapshot_path)
    tables = snapshot_tables(snapshot)
    if MAIN_SHEET not in tables:
        raise ValueError(f'Missing {MAIN_SHEET}')
    issues, main_rows = [], tables[MAIN_SHEET]
    indexes = {}

    def issue(kind, row=None, code=None, **detail):
        item = {'kind': kind, 'code': code, **detail}
        if row:
            item.update(sheet=row.title, row=row.row_number)
        issues.append(item)

    for title in (MAIN_SHEET, *DETAIL_SHEETS.values()):
        index = defaultdict(list)
        field = 'case_id' if title == MAIN_SHEET else '案件編號'
        if title not in tables:
            issue('missing_sheet', sheet=title)
        for row in tables.get(title, []):
            if field not in row.data:
                raise ValueError(f'Missing required header {field} in {title}')
            try:
                key = normalize_case_id(row.data[field])
            except ValueError:
                issue('invalid_case_id', row, raw_id=row.data.get(field))
                continue
            if key != row.data[field]:
                issue('normalized_case_id', row, raw_id=row.data[field], normalized=key)
            index[key].append(row)
        for key, rows in index.items():
            if len(rows) > 1:
                issue('duplicate_case_id', rows[0], case_id=key, rows=[r.row_number for r in rows])
        indexes[title] = index

    main_index = indexes[MAIN_SHEET]
    for code, title in DETAIL_SHEETS.items():
        for key, rows in indexes[title].items():
            if key not in main_index:
                issue('orphan_detail', rows[0], code, case_id=key)

    documents = Counter(str(r.data.get('document_id') or '').strip() for r in main_rows)
    records, normalized, labels = [], [], []
    for main in main_rows:
        raw_id = main.data.get('case_id')
        try:
            key = normalize_case_id(raw_id)
        except ValueError:
            key = None
        case_errors = []
        document = str(main.data.get('document_id') or '').strip()
        if not key or len(main_index[key]) != 1:
            case_errors.append('案件鍵無效或重複，不能選擇其中一列')
        if key and key.rsplit('-C', 1)[0] != document:
            case_errors.append('document_id 與 case_id 不一致')
        try:
            count = int(main.data.get('case_count'))
            if count < 1 or count != documents[document]:
                raise ValueError()
        except (ValueError, TypeError):
            case_errors.append('case_count 與本快照的文件列數不符')
        if case_errors:
            issue('invalid_case', main, case_id=key, reasons=case_errors)

        expected = {code: str(main.data.get(code) or '').strip() for code in ALL_CODES}
        yes_codes = {code for code, val in expected.items() if val == 'YES'}
        final = {v.strip() for v in re.split(r'[;；,，\n]', str(main.data.get('final_r_codes') or '')) if v.strip()}
        label_errors = []
        if final != yes_codes:
            label_errors.append('final_r_codes 與九碼 YES 不一致')
        result = str(main.data.get('case_result') or '').strip()
        if result not in ('受理', '不受理', 'UNCLEAR'):
            label_errors.append('case_result 無效')
        if result == '受理' and any(v != 'NO' for v in expected.values()):
            label_errors.append('受理案件的九碼並非全部 NO')
        if result == '不受理' and not yes_codes:
            label_errors.append('不受理案件沒有 YES')
        if label_errors:
            issue('invalid_labels', main, case_id=key, reasons=label_errors)
        labels.append({'case_id': key, 'source_row': main.row_number, 'expected': expected,
                       'case_result': result, 'final_r_codes': sorted(final), 'errors': label_errors})

        for code in ALL_CODES:
            record = {'case_id': key, 'raw_case_id': raw_id, 'source_row': main.row_number,
                      'code': code, 'expected': expected[code], 'verdict': None,
                      'evaluation': None, 'cohort': None, 'missing_facts': [], 'reason': ''}
            if code in DEFERRED_CODES:
                record.update(status='deferred', reason='依使用者範圍保留接口，等待標註方法，不執行')
                records.append(record)
                continue
            detail_rows = indexes[DETAIL_SHEETS[code]].get(key, []) if key else []
            detail = detail_rows[0] if len(detail_rows) == 1 else None
            mapped = map_row(code, detail)
            invalid = list(case_errors) + mapped.invalid
            comparison_errors = list(label_errors)
            if detail_rows and expected[code] != 'YES':
                comparison_errors.append('細表僅允許主表此碼為 YES 的 Case')
                issue('ineligible_detail', detail_rows[0], code, case_id=key, expected=expected[code])
            if detail and not str(detail.data.get('關鍵依據原文') or '').strip():
                comparison_errors.append('關鍵依據原文缺漏或空白；儲存格座標不等於證據')
                issue('missing_evidence', detail, code, case_id=key)
            if len(detail_rows) > 1:
                invalid.append('細表案件鍵重複')
            reviewed = _reviewed(main) and _reviewed(detail)
            record['cohort'] = 'reviewed' if reviewed else 'exploratory'
            record['detail_row'] = detail.row_number if detail else None
            record['missing_facts'] = mapped.missing
            record['comparison_errors'] = comparison_errors
            normalized.append({'case_id': key, 'source_row': main.row_number, 'code': code,
                               'facts': asdict(mapped.facts), 'candidates': mapped.candidates,
                               'evidence': mapped.evidence, 'missing': mapped.missing, 'invalid': invalid})
            if expected[code] == 'YES' and not detail_rows:
                issue('missing_positive_detail', main, code, case_id=key)
            if invalid:
                record.update(status='invalid_input', reason='；'.join(invalid))
                issue('invalid_rule_input', main, code, case_id=key, reasons=invalid)
            else:
                judged = screen_rule(code, mapped.facts)
                record.update(verdict=judged.verdict.name, reason=judged.reason,
                              computed=judged.computed, remedy=judged.remedy)
                if judged.computed.get('input_errors'):
                    record['status'] = 'invalid_input'
                elif comparison_errors:
                    record.update(status='invalid_input')
                elif expected[code] not in ('YES', 'NO'):
                    record['status'] = 'insufficient'
                    record['missing_facts'] = mapped.missing + ['預期標籤尚未確定']
                elif judged.verdict.name in ('CLEAR', 'BLOCKED'):
                    actual = 'YES' if judged.verdict.name == 'BLOCKED' else 'NO'
                    evaluation = 'matched' if actual == expected[code] else 'mismatched'
                    record.update(evaluation=evaluation, status=evaluation if reviewed else 'unreviewed')
                else:
                    record['status'] = {'INSUFFICIENT':'insufficient', 'DISPUTED':'disputed', 'NOT_COVERED':'unsupported'}[judged.verdict.name]
            records.append(record)

    summary = {'cases': len(main_rows), 'documents': len(documents),
               'active_rules': list(DETAIL_SHEETS), 'deferred_rules': list(DEFERRED_CODES),
               'rule_records': len(records), 'quality_issues': len(issues),
               'case_result_counts': dict(Counter(r.data.get('case_result') for r in main_rows)),
               'by_code': {}}
    for cohort in ('reviewed', 'exploratory'):
        comparable = [r for r in records if r['cohort'] == cohort and r['evaluation']]
        summary[f'{cohort}_comparable'] = len(comparable)
        summary[f'{cohort}_matched'] = sum(r['evaluation'] == 'matched' for r in comparable)
        summary[f'{cohort}_agreement'] = (summary[f'{cohort}_matched']/len(comparable)) if comparable else None
    for code in ALL_CODES:
        subset = [r for r in records if r['code'] == code]
        summary['by_code'][code] = dict(Counter(r['status'] for r in subset))
        summary['by_code'][code]['definitive'] = sum(r['verdict'] in ('CLEAR','BLOCKED') for r in subset)
        summary['by_code'][code]['detail_rows'] = len(tables.get(DETAIL_SHEETS.get(code), []))

    output.mkdir(parents=True, exist_ok=False)
    for filename, rows in [('quality_issues.jsonl',issues), ('normalized_facts.jsonl',normalized),
                           ('expected_labels.jsonl',labels), ('rule_results.jsonl',records)]:
        (output/filename).write_text(''.join(_json(r)+'\n' for r in rows), encoding='utf-8')
    manifest = {'created_at': datetime.now(timezone.utc).isoformat(), 'source': snapshot.get('source'),
                'capture': snapshot.get('capture'), 'snapshot_sha256': snapshot['_sha256'],
                'mapping_version': MAPPING_VERSION, 'engine': _source_version(), 'params': asdict(DEFAULT_PARAMS),
                'scope': list(DETAIL_SHEETS), 'deferred': list(DEFERRED_CODES)}
    (output/'manifest.json').write_text(_json(manifest)+'\n', encoding='utf-8')
    (output/'summary.json').write_text(_json(summary)+'\n', encoding='utf-8')
    from .report import render_report
    (output/'report.md').write_text(render_report(summary, records, issues), encoding='utf-8')
    return summary
