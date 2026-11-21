import json
from pathlib import Path
import subprocess
import sys

import pytest

from test_replay_mapping import seal
from foi_screening.replay.runner import run


def payload(reviewed=True, label='YES'):
    headers=['document_id','case_id','case_count','case_result']+[f'R{i:02}' for i in range(1,10)]+['final_r_codes','標註狀態','檢核狀態']
    labels=['YES','NO',label,'NO','NO','NO','NO','NO','NO']
    main=['115-7','115-7-C1','1','不受理']+labels+['R01; R03' if label=='YES' else 'R01','已完成','已完成']
    return {'schema_version':1,'source':{'spreadsheet_id':'synthetic'}, 'sheets':[
        {'title':'01_Case_Screening','values':[headers,main]},
        {'title':'03_R03_未先向金融服務業申訴','values':[
            ['案件編號','先行申訴缺失類型','標註狀態','檢核狀態','關鍵依據原文'],
            ['115-7-c1','先行申訴對象非本案相對人','已完成','已完成' if reviewed else '未完成','合成證據：向其他公司申訴，本案相對人無紀錄。']]},
    ]}


def result_rows(out):
    return [json.loads(line) for line in (out/'rule_results.jsonl').read_text(encoding='utf-8').splitlines()]


def test_renamed_detail_sheet_retains_actual_evidence_title(tmp_path):
    data = payload()
    data['sheets'][1]['title'] = 'R03_未先向金融服務業申訴'
    summary = run(seal(tmp_path, data), tmp_path/'renamed')
    assert summary['reviewed_comparable'] == 1
    assert summary['reviewed_matched'] == 1
    assert 'R03_未先向金融服務業申訴' in (tmp_path/'renamed/normalized_facts.jsonl').read_text(encoding='utf-8')


def test_duplicate_old_and_new_detail_names_are_rejected(tmp_path):
    data = payload()
    data['sheets'].append({**data['sheets'][1], 'title': 'R03_未先向金融服務業申訴'})
    with pytest.raises(ValueError, match='重複對應'):
        run(seal(tmp_path, data), tmp_path/'duplicate')


def test_full_workbook_does_not_parse_deferred_or_instruction_tables(tmp_path):
    data = payload()
    data['sheets'].append({'title': 'R01_申請不合程式', 'values': [['說明', '說明']]})
    data['sheets'].append({'title': '標註規則與欄位說明', 'values': [['說明', '說明']]})
    assert run(seal(tmp_path, data), tmp_path/'full')['reviewed_matched'] == 1


def test_end_to_end_no_source_mutation_and_deferred_interfaces(tmp_path):
    source=seal(tmp_path, payload())
    before=source.read_bytes()
    out=tmp_path/'run'
    summary=run(source, out)
    assert source.read_bytes()==before
    rows=result_rows(out)
    assert len(rows)==9
    assert {r['code'] for r in rows if r['status']=='deferred'}=={'R01','R02','R06','R09'}
    r03=next(r for r in rows if r['code']=='R03')
    assert r03['verdict']=='BLOCKED' and r03['status']=='matched'
    assert summary['reviewed_comparable']==1
    assert summary['reviewed_matched']==1
    assert summary['by_code']['R04']['insufficient']==1
    facts=(out/'normalized_facts.jsonl').read_text(encoding='utf-8')
    assert 'final_r_codes' not in facts and 'case_result' not in facts
    assert json.loads((out/'manifest.json').read_text(encoding='utf-8'))['snapshot_sha256']


def test_labels_change_comparison_not_facts_or_prediction(tmp_path):
    p=seal(tmp_path,payload(label='YES'))
    run(p,tmp_path/'one')
    p=seal(tmp_path,payload(label='NO'))
    run(p,tmp_path/'two')
    one=next(r for r in result_rows(tmp_path/'one') if r['code']=='R03')
    two=next(r for r in result_rows(tmp_path/'two') if r['code']=='R03')
    assert one['verdict']==two['verdict']=='BLOCKED'
    assert one['status']=='matched' and two['status']=='invalid_input'
    assert two['evaluation'] is None
    assert (tmp_path/'one/normalized_facts.jsonl').read_bytes()==(tmp_path/'two/normalized_facts.jsonl').read_bytes()


def test_unreviewed_rows_not_in_reviewed_denominator(tmp_path):
    summary=run(seal(tmp_path,payload(reviewed=False)),tmp_path/'out')
    assert summary['reviewed_comparable']==0
    assert summary['reviewed_agreement'] is None
    assert summary['exploratory_comparable']==1


def test_normalized_duplicate_main_keys_block_ambiguous_join(tmp_path):
    data=payload()
    duplicate=list(data['sheets'][0]['values'][1]);duplicate[1]='115-7-c1'
    data['sheets'][0]['values'].append(duplicate)
    summary=run(seal(tmp_path,data),tmp_path/'out')
    assert summary['reviewed_comparable']==0
    assert all(r['status']=='invalid_input' for r in result_rows(tmp_path/'out') if r['code']=='R03')


def test_unknown_id_and_orphan_details_are_reported(tmp_path):
    data=payload()
    data['sheets'][1]['values'].append(['115-999-C1','先行申訴對象非本案相對人','已完成','已完成'])
    data['sheets'][0]['values'][1][1]='bad-key'
    run(seal(tmp_path,data),tmp_path/'out')
    issues=[json.loads(line) for line in (tmp_path/'out/quality_issues.jsonl').read_text(encoding='utf-8').splitlines()]
    assert {'invalid_case_id','orphan_detail'} <= {i['kind'] for i in issues}


def test_existing_output_is_never_overwritten(tmp_path):
    p=seal(tmp_path,payload());out=tmp_path/'out'
    run(p,out)
    before=(out/'rule_results.jsonl').read_bytes()
    with pytest.raises(FileExistsError):
        run(p,out)
    assert before==(out/'rule_results.jsonl').read_bytes()


def test_cli_offline_repeat_has_identical_results(tmp_path):
    path=seal(tmp_path,payload())
    for name in ('first','second'):
        proc=subprocess.run([sys.executable,'-B','-m','foi_screening.replay','--snapshot',str(path),'--output',str(tmp_path/name)],capture_output=True)
        assert proc.returncode==0, proc.stderr.decode(errors='replace')
    assert (tmp_path/'first/rule_results.jsonl').read_bytes()==(tmp_path/'second/rule_results.jsonl').read_bytes()


def test_detail_without_review_columns_remains_exploratory(tmp_path):
    data=payload()
    data['sheets'][1]['values']=[r[:2]+r[4:] for r in data['sheets'][1]['values']]
    summary=run(seal(tmp_path,data),tmp_path/'out')
    assert summary['reviewed_comparable']==0
    assert summary['exploratory_comparable']==1

@pytest.mark.parametrize('evidence', [None,'','   '])
def test_missing_evidence_excludes_reviewed_comparison_without_erasing_prediction(tmp_path,evidence):
    data=payload()
    data['sheets'][1]['values']=[r[:4] for r in data['sheets'][1]['values']]
    if evidence is not None:
        data['sheets'][1]['values'][0].append('關鍵依據原文')
        data['sheets'][1]['values'][1].append(evidence)
    summary=run(seal(tmp_path,data),tmp_path/'out')
    r03=next(r for r in result_rows(tmp_path/'out') if r['code']=='R03')
    assert r03['status']=='invalid_input'
    assert r03['verdict']=='BLOCKED'
    assert r03['evaluation'] is None
    assert summary['reviewed_comparable']==0
    issues=[json.loads(x) for x in (tmp_path/'out/quality_issues.jsonl').read_text(encoding='utf-8').splitlines()]
    assert any(x['kind']=='missing_evidence' for x in issues)


def test_nonpositive_detail_is_quality_failure_not_rule_mismatch(tmp_path):
    data=payload(label='NO')
    summary=run(seal(tmp_path,data),tmp_path/'out')
    r03=next(r for r in result_rows(tmp_path/'out') if r['code']=='R03')
    assert r03['status']=='invalid_input'
    assert r03['verdict']=='BLOCKED' and r03['expected']=='NO'
    assert r03['evaluation'] is None
    assert summary['reviewed_comparable']==0
    issues=[json.loads(x) for x in (tmp_path/'out/quality_issues.jsonl').read_text(encoding='utf-8').splitlines()]
    assert any(x['kind']=='ineligible_detail' for x in issues)
