"""Synthetic data only: no source judgments or personal annotation data."""
import hashlib
import json
from datetime import date

import pytest

from foi_screening.replay.source import SourceRow, load_snapshot, normalize_case_id, read_table
from foi_screening.replay.mapping import map_row
from foi_screening.facts import PriorEvaluation


def row(data, title='test'):
    return SourceRow(title=title, row_number=2, data=data, columns={k:i+1 for i,k in enumerate(data)})


def seal(tmp_path, payload):
    path=tmp_path/'snapshot.json'
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
    path.with_suffix('.sha256').write_text(hashlib.sha256(path.read_bytes()).hexdigest(), encoding='ascii')
    return path


def test_changed_snapshot_is_rejected(tmp_path):
    path=seal(tmp_path, {'schema_version':1, 'sheets':[]})
    path.write_text('{}', encoding='utf-8')
    with pytest.raises(ValueError, match='SHA-256'):
        load_snapshot(path)


def test_header_names_and_source_rows_survive_blank_cells():
    sheet={'title':'main', 'values':[['case_id\nCase 編號','review_note\n備註'],[],[' 115-7-c1 ','memo']]}
    rows=read_table(sheet)
    assert rows[0].row_number==3
    assert rows[0].data['review_note']=='memo'
    assert normalize_case_id(rows[0].data['case_id'])=='115-7-C1'


def test_duplicate_headers_fail_instead_of_overwriting_values():
    with pytest.raises(ValueError, match='header'):
        read_table({'title':'main','values':[['case_id','case_id'],['a','b']]})


def test_r03_no_record_is_unknown_but_wrong_respondent_is_explicit():
    unknown=map_row('R03', row({'先行申訴缺失類型':'無本案先行申訴紀錄'}))
    assert unknown.facts.has_complained is None
    known=map_row('R03', row({'先行申訴缺失類型':'先行申訴對象非本案相對人'}))
    assert known.facts.has_complained is False
    assert known.evidence[0]['row']==2


def test_r07_requires_both_event_and_claim_identity():
    data={'前案終結情形':'未表示接受而不成立', '同一事件判斷基礎':'核心事實／交易事件相同;實質請求目的相同'}
    assert map_row('R07', row(data)).facts.prior_evaluation is PriorEvaluation.REJECTED
    data['同一事件判斷基礎']='當事人／相對人相同'
    assert map_row('R07', row(data)).facts.prior_evaluation is None


def test_r05_dates_keep_distinct_event_semantics():
    mapped=map_row('R05', row({'金融服務業收受申訴日期':'2025/08/05',
        '申請人收受處理結果日期':'2025/08/26', '評議中心收文日期':'2025/12/19'}))
    assert mapped.facts.complaint_date is None
    assert mapped.facts.application_date is None
    assert mapped.facts.proceedings is None
    assert mapped.facts.reply_received_date==date(2025,8,26)
    assert mapped.candidates['評議中心收文日期']=='2025-12-19'


def test_bad_date_is_reported_not_silently_dropped():
    mapped=map_row('R04', row({'申訴日期':'2025/02/30', '評議日期':'115/01/05'}))
    assert len(mapped.invalid)==2


def test_r08_does_not_assume_same_event_from_free_text():
    mapped=map_row('R08', row({'既有程序類型':'和解成立','既有程序處理內容':'looks similar'}))
    assert mapped.facts.proceedings is None
    assert mapped.candidates['proceeding_kind']=='SETTLEMENT'


@pytest.mark.parametrize('code', ['R01','R02','R06','R09'])
def test_deferred_mapping_does_not_read_row(code):
    with pytest.raises(ValueError):
        map_row(code, row({'anything':'ignored'}))

@pytest.mark.parametrize('formal,kind', [('和解成立','SETTLEMENT'),('調解成立','MEDIATION_OTHER'),('調處成立','MEDIATION_FOI'),('仲裁成立','ARBITRATION'),('法院判決確定','COURT_JUDGMENT'),('評議成立','EVALUATION')])
def test_r08_preserves_all_formal_procedure_candidates_without_inventing_scope(formal,kind):
    mapped=map_row('R08',row({'既有程序類型':formal}))
    assert mapped.candidates['proceeding_kind']==kind
    assert mapped.facts.proceedings is None


@pytest.mark.parametrize('outcome,expected', [('撤回','WITHDRAWN'),('明示拒絕而不成立','REJECTED'),('其他不成立情形','REJECTED')])
def test_r07_maps_formal_outcomes_only_with_both_identity_facts(outcome,expected):
    data={'前案終結情形':outcome,'同一事件判斷基礎':'核心事實／交易事件相同;實質請求目的相同'}
    mapped=map_row('R07',row(data))
    assert mapped.facts.prior_evaluation is not None
    assert mapped.facts.prior_evaluation.name==expected
    data['同一事件判斷基礎']='核心事實／交易事件相同'
    assert map_row('R07',row(data)).facts.prior_evaluation is None


def test_r05_preserves_distinct_dates_without_inventing_submission_or_other_paths():
    mapped=map_row('R05',row({'金融服務業收受申訴日期':'2025/01/02','相對人回覆日期':'2025/01/30',
        '申請人收受處理結果日期':'2025/02/05','評議中心收文日期':'2025/04/01'}))
    assert getattr(mapped.facts,'complaint_received_date',None)==date(2025,1,2)
    assert getattr(mapped.facts,'business_reply_date',None)==date(2025,1,30)
    assert getattr(mapped.facts,'center_received_date',None)==date(2025,4,1)
    assert mapped.facts.reply_received_date==date(2025,2,5)
    assert mapped.facts.complaint_date is None
    assert mapped.facts.application_date is None
    assert mapped.facts.proceedings is None


def test_r05_missing_lists_needed_facts_not_independent_submission_dates():
    mapped=map_row('R05',row({'金融服務業收受申訴日期':'2025/01/02','相對人回覆日期':'2025/01/30',
        '申請人收受處理結果日期':'2025/02/05','評議中心收文日期':'2025/04/01'}))
    assert len(mapped.missing)==1
    assert '其他調處' in mapped.missing[0]
    incomplete=map_row('R05',row({'評議中心收文日期':'2025/04/01'}))
    assert any('業者收受申訴日' in x for x in incomplete.missing)
    assert any('業者回覆' in x for x in incomplete.missing)
    assert any('申請人收受處理結果日' in x for x in incomplete.missing)
