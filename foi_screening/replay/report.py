"""Human-readable coverage and blockers, never a model accuracy claim."""


def render_report(summary, records, issues):
    lines = ['# 五碼標註串接回放報告', '',
        '本報告為歷史標註回放，不代表申請前預測準確率或法律正確性認證。', '',
        f'匯入 {summary["cases"]} 個 Case、{summary["documents"]} 份文件。',
        '啟用 R03、R04、R05、R07、R08；R01、R02、R06、R09 保留接口，未執行。', '',
        '| 規則 | 細表列數 | 明確判定數 | 已檢核相符 | 已檢核不符 | 未檢核可比較 | 資料不足 | 輸入問題 | 有爭議 |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for code in summary['active_rules']:
        s = summary['by_code'][code]
        lines.append(f'| {code} | {s["detail_rows"]} | {s["definitive"]} | {s.get("matched",0)} | {s.get("mismatched",0)} | {s.get("unreviewed",0)} | {s.get("insufficient",0)} | {s.get("invalid_input",0)} | {s.get("disputed",0)} |')
    lines += ['', '## 可比較範圍', '',
        f'- 主表與細表皆完成標註及檢核：可比較 {summary["reviewed_comparable"]} 項，其中相符 {summary["reviewed_matched"]} 項。',
        f'- 尚未滿足雙表檢核條件：可比較 {summary["exploratory_comparable"]} 項，其中相符 {summary["exploratory_matched"]} 項，另列探索組。',
        '- 計數單位是 Case × 規則；四個暫緩碼及資料不足者不進入可比較分母。',
        '- 細表主表資格不符或關鍵依據原文缺漏，列為 invalid_input，不計入相符／不符；原標籤、映射事實與引擎判定仍分開保存。',
        '- Evidence 閘門只確認原文欄非空，不證明來源 PDF 正確、引文真實或中心認定充分；這些仍需人工核對。',
        '- 相符率分母為零時為 N/A。全為不受理的資料不能提供完整分類準確率。',
        '- 細表本身包含事後人工判斷，回放不能驗證事實抽取或消除選擇偏誤。', '',
        '## 已有細表但尚待確認的事實', '']
    for r in records:
        if r.get('detail_row') and r['missing_facts']:
            lines.append(f'- {r["case_id"]} / {r["code"]}（細表第 {r["detail_row"]} 列）：'+'；'.join(r['missing_facts']))
    lines += ['', '## 資料品質', '', f'共 {len(issues)} 項提示／問題；完整內容見 quality_issues.jsonl。', '']
    for i in issues:
        row = f'第 {i["row"]} 列' if 'row' in i else ''
        lines.append(f'- {i["kind"]}：{i.get("sheet","")} {row} {i.get("code") or ""} {i.get("case_id") or ""}')
    for r in records:
        if r.get('comparison_errors'):
            lines.append(f'- {r["case_id"]} / {r["code"]} 比較資格問題：'+'；'.join(r['comparison_errors']))
    lines += ['', '## 產物', '',
        '- manifest.json：來源快照、程式雜湊、參數及啟用範圍。',
        '- normalized_facts.jsonl：已映射事實、候選欄位、來源儲存格與缺漏。',
        '- expected_labels.jsonl：獨立保存標註答案。',
        '- rule_results.jsonl：每筆 Case 的九碼接口結果，包含 deferred。',
        '- summary.json：分組計數；quality_issues.jsonl：來源品質問題。', '']
    return '\n'.join(lines)
