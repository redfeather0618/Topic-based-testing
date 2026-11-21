"""Explicit retrospective mappings. No labels or free-text inference here."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
import re

from ..facts import RuleFacts, PriorEvaluation
from .source import SourceRow, DETAIL_SHEETS

MAPPING_VERSION = 'five-rules-v2'


@dataclass(frozen=True)
class MappedFacts:
    facts: RuleFacts
    evidence: list[dict] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    candidates: dict = field(default_factory=dict)
    invalid: list[str] = field(default_factory=list)


def _date(value: object) -> date:
    text = str(value).strip()
    western = re.fullmatch(r'(\d{4})[/-](\d{1,2})[/-](\d{1,2})', text)
    roc = re.fullmatch(r'民國(\d{2,3})年(\d{1,2})月(\d{1,2})日', text)
    if western:
        year, month, day = map(int, western.groups())
        if year < 1912:
            raise ValueError('ambiguous calendar')
    elif roc:
        year, month, day = map(int, roc.groups())
        year += 1911
    else:
        raise ValueError('date requires explicit calendar')
    return date(year, month, day)


def map_row(code: str, row: SourceRow | None) -> MappedFacts:
    if code not in DETAIL_SHEETS:
        raise ValueError(f'Deferred or unknown rule: {code}')
    if row is None:
        return MappedFacts(RuleFacts(), missing=['缺少此規則的細部事實列；不以主表標籤補值'])
    data, facts, evidence, missing, candidates, invalid = row.data, {}, [], [], {}, []

    def get(name):
        return str(data.get(name) or '').strip()

    def assign(name, value, *source_fields):
        facts[name] = value
        for source_field in source_fields:
            evidence.append({**row.reference(source_field), 'target': name,
                             'kind': 'retrospective_annotation', 'mapping_version': MAPPING_VERSION})

    def candidate_date(name):
        if not get(name):
            return None
        try:
            value = _date(get(name))
        except ValueError:
            invalid.append(f'{name}: 無效或曆法不明的日期 {get(name)!r}')
            return None
        candidates[name] = value.isoformat()
        evidence.append({**row.reference(name), 'target': name, 'kind': 'candidate_date'})
        return value

    if code == 'R03':
        kind = get('先行申訴缺失類型')
        if kind == '先行申訴對象非本案相對人':
            assign('has_complained', False, '先行申訴缺失類型')
        else:
            candidates['先行申訴缺失類型'] = kind
            missing.append('需確認本案是否實際先向相對人申訴；無紀錄或未知類型不能當成未申訴')
    elif code == 'R04':
        candidate_date('申訴日期')
        candidate_date('評議日期')
        missing.extend(['申訴日期與申請日期的事件定義須確認', '缺少申請時業者是否已回覆的明確欄位'])
    elif code == 'R05':
        for source, target in [('金融服務業收受申訴日期', 'complaint_received_date'),
                               ('相對人回覆日期', 'business_reply_date'),
                               ('評議中心收文日期', 'center_received_date')]:
            value = candidate_date(source)
            if value:
                assign(target, value, source)
        received = candidate_date('申請人收受處理結果日期')
        candidates['60日期限起算類型'] = get('60日期限起算類型')
        if received:
            assign('reply_received_date', received, '申請人收受處理結果日期')
            assign('business_replied', True, '申請人收受處理結果日期')
            assign('has_complained', True, '申請人收受處理結果日期')
        for target, message in [
            ('complaint_received_date', '缺少已確認的業者收受申訴日，不能計算30日處理期限'),
            ('business_reply_date', '缺少業者回覆行為日，不能確認是否在30日內回覆'),
            ('reply_received_date', '缺少申請人收受處理結果日；亦未有明確未回覆狀態'),
            ('center_received_date', '缺少中心收文日，無法確認歷史期限比較終點'),
        ]:
            if target not in facts:
                missing.append(message)
        missing.append('未確認是否存在其他調處／調解期限路徑')
    elif code == 'R07':
        outcome = get('前案終結情形')
        basis = set(re.split(r'[;；\n]', get('同一事件判斷基礎')))
        basis = {item.strip() for item in basis}
        identity = {'核心事實／交易事件相同', '實質請求目的相同'} <= basis
        if identity and outcome in ('未表示接受而不成立', '明示拒絕而不成立', '其他不成立情形', '撤回'):
            prior = PriorEvaluation.WITHDRAWN if outcome == '撤回' else PriorEvaluation.REJECTED
            assign('prior_evaluation', prior, '前案終結情形', '同一事件判斷基礎')
        else:
            missing.append('前案結果或同一事件的結構化依據尚不足')
        candidates.update({'前案終結情形': outcome, '同一事件判斷基礎': get('同一事件判斷基礎')})
    elif code == 'R08':
        kind = {'和解成立': 'SETTLEMENT', '調解成立': 'MEDIATION_OTHER', '調處成立': 'MEDIATION_FOI',
                '仲裁成立': 'ARBITRATION', '法院判決確定': 'COURT_JUDGMENT', '評議成立': 'EVALUATION'}.get(get('既有程序類型'))
        if kind:
            candidates.update(proceeding_kind=kind, proceeding_status='CONCLUDED')
            evidence.append({**row.reference('既有程序類型'), 'kind': 'candidate_proceeding'})
        missing.append('需結構化確認既有程序與本次申請為同一事件；不從自由文字推論')
    return MappedFacts(RuleFacts(**facts), evidence, missing, candidates, invalid)
