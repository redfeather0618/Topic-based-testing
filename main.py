from fastapi import FastAPI
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta
from pathlib import Path
import os

from screening_api import router as screening_router

app = FastAPI(title="金融消費評議資格智慧判定系統 API")

# 若前端由另一個來源提供，請以逗號分隔設定精確來源；同源提供頁面不需 CORS。
allowed_origins = [
    origin.strip()
    for origin in os.getenv("FOI_ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]
if allowed_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

BASE_DIR = Path(__file__).resolve().parent
INDEX_HTML_PATH = BASE_DIR / "index.html"

app.include_router(screening_router)

# 首頁路由
@app.get("/", response_class=HTMLResponse)
def read_index():
    if INDEX_HTML_PATH.exists():
        with open(INDEX_HTML_PATH, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>找不到 index.html 檔案，請確認 index.html 與 main.py 放在同一資料夾中。</h1>"

# 1. 對齊 index.html 表單的完整資料結構
class DisputeCaseRequest(BaseModel):
    industry: str                      # 涉及金融產業類別 (銀行業、人身保險等)
    institutionName: str               # 金融機構名稱
    issueCategory: str                 # 爭議類別主軸
    hasComplained: bool                # 是否已提出正式申訴
    complainDate: Optional[str] = None # 送出申訴日期 (YYYY-MM-DD)
    replyStatus: str                   # 回覆狀態 (replied_rejected / not_replied)
    replyDate: Optional[str] = None    # 收到回覆日期 (YYYY-MM-DD)
    courtDetermined: bool              # 是否已法院判決確定或調解成立
    incidentDate: Optional[str] = None # 爭議事件發生日期 (YYYY-MM-DD)
    claimAmount: float                 # 爭議請求金額 (NTD)
    incidentDetail: str                # 爭議經過事實陳述

# 2. 核心法規判定 API (完全同步前端 evaluateStatutoryRules 邏輯)
@app.post("/api/v1/analyze")
def analyze_dispute(case: DisputeCaseRequest):
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    is_binding_limit = case.claimAmount <= 1200000

    # 規則 A：司法既判力檢核 (金保法第 24 條)
    if case.courtDetermined:
        return build_response("ineligible_court", is_binding_limit, 0, "", case)

    # 規則 B：先行申訴前置程序檢核 (金保法第 13 條)
    if not case.hasComplained or not case.complainDate:
        return build_response("ineligible_nocomplain", is_binding_limit, 0, "", case)

    comp_date = datetime.strptime(case.complainDate, "%Y-%m-%d")

    # 規則 C：業者尚未回覆 (需滿 30 日等待期，且未逾 90 日總期限)
    if case.replyStatus == "not_replied":
        days_since_complain = (today - comp_date).days
        if days_since_complain < 30:
            can_apply_date = comp_date + timedelta(days=30)
            return build_response(
                "pending_wait",
                is_binding_limit,
                30 - days_since_complain,
                can_apply_date.strftime("%Y/%m/%d"),
                case
            )
        else:
            expire_date = comp_date + timedelta(days=90)
            days_left = (expire_date - today).days
            if days_left < 0:
                return build_response(
                    "ineligible_timeout",
                    is_binding_limit,
                    abs(days_left),
                    expire_date.strftime("%Y/%m/%d"),
                    case
                )
            return build_response(
                "eligible_unreplied",
                is_binding_limit,
                days_left,
                expire_date.strftime("%Y/%m/%d"),
                case
            )

    # 規則 D：業者已回覆但不服結果 (自收受回覆翌日起算 60 日內)
    else:
        rep_date = datetime.strptime(case.replyDate, "%Y-%m-%d")
        deadline = rep_date + timedelta(days=60)
        days_left = (deadline - today).days
        if days_left < 0:
            return build_response(
                "ineligible_timeout",
                is_binding_limit,
                abs(days_left),
                deadline.strftime("%Y/%m/%d"),
                case
            )
        return build_response(
            "eligible_replied",
            is_binding_limit,
            days_left,
            deadline.strftime("%Y/%m/%d"),
            case
        )

def build_response(status: str, is_binding_limit: bool, days_number: int, deadline_str: str, case: DisputeCaseRequest):
    # 預留未來接入 LLM 或向量資料庫的語意分析摘要欄位
    ai_summary = (
        f"【後端法規引擎判定】針對「{case.institutionName}」（{case.industry}）之「{case.issueCategory}」爭議，"
        f"請求金額 NT$ {case.claimAmount:,.0f} 元。"
    )
    if status in ["eligible_replied", "eligible_unreplied"]:
        ai_summary += " 經檢核已符合金保法第 13 條先行申訴與時效要件，建議備齊申訴紀錄與往來憑證送件。"
    elif status == "pending_wait":
        ai_summary += f" 目前仍處於業者 30 日法定處理期，建議於 {deadline_str} 後若仍無結果再行送件。"
    else:
        ai_summary += " 本案目前不符評議中心法定受理要件，請依檢核明細調整救濟途徑。"

    return {
        "api_status": "success",
        "status": status,
        "isBindingLimit": is_binding_limit,
        "daysNumber": days_number,
        "deadlineStr": deadline_str,
        "aiAnalysis": ai_summary
    }

# 3. 匯出評議申請書草稿 API
@app.post("/api/v1/export-application", response_class=PlainTextResponse)
def export_application(case: DisputeCaseRequest):
    content = f"""====================================================
        財團法人金融消費評議中心 評議申請書（系統草稿）
====================================================
【申請人基本資料】
姓    名：____________________ （請親筆簽名或蓋章）
聯絡電話：____________________
通訊地址：________________________________________

【相對人（金融服務業）資料】
金融業別：{case.industry}
機構名稱：{case.institutionName}

【爭議標的與請求事項】
爭議類別：{case.issueCategory}
事件發生日：{case.incidentDate or '未填寫'}
先行申訴日：{case.complainDate or '未填寫'}
請求金額：新臺幣 {case.claimAmount:,.0f} 元整

【事實及理由陳述】
{case.incidentDetail}

【檢附證據清單（請自行勾選並隨附影本）】
[ ] 1. 身分證明文件影本
[ ] 2. 向金融機構提出申訴之證明文件（如存證信函、客服紀錄、電子郵件）
[ ] 3. 金融機構之正式回覆函文（若已逾 30 日未回覆則免附）
[ ] 4. 相關契約、對帳單、刷卡明細或理賠拒絕通知書

※ 本文件由「金融消費評議資格智慧判定系統」自動產生，正式送件前請再次核對個人資料與證據影本。
"""
    return content

