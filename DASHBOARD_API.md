# 組員 B：統計 API 串接工作底稿

## 目前範圍

優先完成標註統計資料讀取與分類呈現的 API 介面，為前端組員提供可重用的 client。相似案件僅保留搜尋模板，不實作相似度、向量或語意檢索。Line Bot API 暫不處理；需要設計或串接時先和組員 B 確認。

## 服務邊界

- `C:\\Users\\sandy\\OneDrive\\桌面\\專題專題\\main.py`：網站與前次本機五碼檢核 API。
- ZIP 專案中的 `foi_api`：爬蟲與人工標註統計 API，統計路徑為 `/api/v1/annotations/...`。

統計 API 目前尚未部署公網，且桌面網站服務不是 `foi_api`。client 的 `baseUrl` 要使用組長啟動後提供的統計 API 網址，不能只把桌面網站網址當成統計服務網址。

## 已準備的串接檔案

- `api/annotations-client.mjs`：沿用組長提供的正式範例；權杖與服務網址由執行時傳入。
- `tests/annotations-client.test.mjs`：以合成回應離線驗證固定資料版本、Bearer 權杖及 401 錯誤處理。

前端先呼叫 `dashboard(filters)`：client 先讀 current 版本，再以同一 `dataset_version` 查 overview、R-code 統計與分類分布。分類目前支援 `dispute_category` 或 `document_type`；不擅自新增其他分類口徑。各圖表下鑽案件清單時沿用同一份 `dashboard.filters`，避免資料版本或母數不同。

```javascript
import { createAnnotationsClient } from "./api/annotations-client.mjs";
const api = createAnnotationsClient(apiBaseUrl, apiToken);
const dashboard = await api.dashboard({ cohort: "annotated" });
```

## 驗證

```powershell
node --test tests/annotations-client.test.mjs
```

此測試使用假資料，不會連線到組長服務，也不會讀取真實案件內容。

## 待取得的組員資料

1. 組長授權的標註快照 JSON 與同名 `.sha256` 檔，供建立／更新後端統計資料版本。API 專案不含真實快照，尚未拿到時不能產生真實統計。
2. 統計 API 的啟動網址、執行期間權杖取得方式及允許的前端來源。請勿把權杖提交 Git 或貼在聊天中。
3. 前端組員的儀表板頁面或預期欄位／圖表清單，以及「統計數據重新分類」要使用的分類定義。組長 API 現行只支援爭議類別與文件類型分組。

拿到以上資訊後，先完成授權快照匯入及品質報告檢查，再做儀表板 API 實連與前端下鑽驗收。部署與跨組串接前，依組長規範使用 Bearer 權杖及精確 CORS 來源。
