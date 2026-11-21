# 前後端串接第一階段：五碼檢核 API

本地開發用 FastAPI 端點：`POST /api/v1/screening`。網頁送出流程已呼叫此端點；既有的 `/api/v1/analyze` 暫時保留相容，但不再由頁面使用。

## 範圍

端點只執行組長規範允許的新整合五碼：R03、R04、R05、R07、R08。回應逐碼提供 `verdict`、`reason`、`remedy`、`legal_basis`、`computed` 等引擎資料。這不是受理保證或法律意見。

## 輸入欄位

JSON 使用 snake_case。日期格式為 `YYYY-MM-DD`。可以省略未知欄位或明確傳 `null`；未知不會被當成「否」。

- `application_date`：預計申請日期；未提供時以服務端今天為預設值。
- `has_complained`、`complaint_date`：是否已申訴、提出申訴日期。
- `complaint_received_date`：業者實際收受申訴日期。現有網頁沒有此欄位，未回覆案件的 R04/R05 可能回資料不足；不得拿提出日期代替。
- `business_replied`、`business_reply_date`、`reply_received_date`：回覆狀態、業者作成回覆日、申請人收受回覆日。現有「收到正式回覆日期」只能對應 `reply_received_date`。
- `center_received_date`：評議中心實際收文日期；申請前通常未知。
- `prior_evaluation`：曾否依本法申請評議及其結果。現有網頁未詢問，會保持未知。
- `proceedings`：其他爭議處理程序。現有網頁欄位不足以完整描述程序種類、狀態、日期及是否涵蓋本案；不得把現有「法院判決／調解成立」選項直接當成完整程序清單。

最小請求範例：

```json
{
  "application_date": "2026-11-15",
  "has_complained": true,
  "complaint_date": "2026-10-01",
  "business_replied": false
}
```

本例未提供業者實際收受日，因此 R04/R05 可能為「資料不足」。

## 測試與啟動

在此資料夾以 PowerShell 執行：

```powershell
python -m unittest discover -s tests -p 'test_screening_api.py' -v
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

此端點目前只供本機同源開發，尚未加 Bearer 權杖；不要用 `0.0.0.0` 對外提供或部署。跨電腦／部署前須先依組長 API 契約加入權杖驗證。API 文件：`http://127.0.0.1:8000/docs`。前端與 API 同源時不需 CORS；若由其他網址提供頁面，啟動前設定精確來源，例如 `$env:FOI_ALLOWED_ORIGINS = 'http://localhost:5173'`，不要使用萬用字元。引擎完整回歸測試需安裝 `pytest` 後執行 `python -m pytest tests/foi_screening -q`。

## 尚未完成

目前 5 項 unittest 涵蓋五碼範圍、未知資料保留、已知否的判定、日期驗證、前端欄位映射與 OpenAPI 路由登錄；另外已通過 Python 編譯及 Node.js 語法檢查。受執行環境的 loopback socket 權限限制，尚未完成瀏覽器至本機 API 的真實 HTTP 往返驗收。上游完整 pytest 回歸測試尚未執行，因目前環境沒有 pytest 且網路安裝受限。
