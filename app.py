import os
import logging
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator, EmailStr
from dotenv import load_dotenv
from groq import AsyncGroq
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ⚡ KARMA CLAIMS — ENGINE v3.2 (FINAL PRODUCTION)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")
logger = logging.getLogger("karma-claims")

load_dotenv()
API_KEY = os.getenv("GROQ_API_KEY")
if not API_KEY:
    raise RuntimeError("[FATAL] GROQ_API_KEY is not set.")

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")

# ── 1. VOLATILE MEMORY (Dashboard Stats) ──
SYSTEM_METRICS = {
    "total_recovered": 450000, 
    "cases_won": 142,
    "active_users": 890
}

# ── 2. THE VERIFIED DB (High-Priority Targets) ──
VERIFIED_DB: dict[str, dict] = {
    "Google Pay (Google India Digital Services)": {
        "email": "nodal-gpay@google.com", "industry": "Fintech", "regulator": "RBI",
        "twitter": "@GooglePayIndia", "portal": "https://support.google.com/pay/india/"
    },
    "HDFC Bank (HDFC Bank Limited)": {
        "email": "pno@hdfcbank.com", "industry": "Banking", "regulator": "RBI",
        "twitter": "@HDFC_Bank_Cares", "portal": "https://www.hdfcbank.com/personal/need-help"
    },
    "Swiggy (Bundl Technologies Pvt Ltd)": {
        "email": "grievances@swiggy.in", "industry": "E-Commerce", "regulator": "CCPA",
        "twitter": "@SwiggyCares", "portal": "https://www.swiggy.com/contact"
    }
}

limiter = Limiter(key_func=get_remote_address)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("⚡ Karma Claims v3.2 is online and secured.")
    yield

app = FastAPI(title="Karma Claims v3.2", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(CORSMiddleware, allow_origins=ALLOWED_ORIGINS, allow_credentials=False, allow_methods=["*"], allow_headers=["*"])

client = AsyncGroq(api_key=API_KEY)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SERVER HEALTH CHECK (For Render)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@app.get("/health")
async def health_check():
    return {"status": "Live", "version": "3.2", "systems_online": 7}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# BULLETPROOF SCHEMAS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class DisputeRequest(BaseModel):
    user_name: str
    user_email: EmailStr
    user_phone: str
    company_name: str
    order_id: str
    disputed_amount: str
    complaint_details: str

    @field_validator('disputed_amount')
    def sanitize_amount(cls, v):
        clean = ''.join(filter(lambda x: x.isdigit() or x == '.', str(v)))
        return clean if clean else "0"

class ChatRequest(BaseModel):
    user_message: str

class BSDetectorRequest(BaseModel):
    corporate_reply: str

class OutcomeRequest(BaseModel):
    amount_recovered: float
    company_name: str

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# THE CORE ENGINE (Dynamic Prompting)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@app.post("/generate-draft")
@limiter.limit("5/minute")
async def generate_legal_draft(request: Request, payload: DisputeRequest):
    legal_framework = "Consumer Protection Act (CCPA) 2019"
    if payload.company_name in VERIFIED_DB and VERIFIED_DB[payload.company_name].get("regulator") == "RBI":
        legal_framework = "Reserve Bank of India (RBI) rules for unauthorized transactions"

    prompt = f"""
    You are a fierce Indian corporate lawyer. Draft a formal legal grievance notice for {payload.user_name} against {payload.company_name}.
    Details: Order ID {payload.order_id}, Amount ₹{payload.disputed_amount}.
    Complaint: {payload.complaint_details}
    
    Rules:
    1. Base your legal threats strictly on the {legal_framework}.
    2. Demand a resolution within 48 hours or threaten escalation to the Nodal Officer/Ombudsman.
    3. Keep it highly professional, intimidating, and ready to send. DO NOT include placeholders like [Your Address].
    4. Sign off with:
       {payload.user_name}
       Ph: {payload.user_phone}
    """
    try:
        response = await client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": "You are a legal AI."}, {"role": "user", "content": prompt}],
            temperature=0.3, max_tokens=600
        )
        target_email = VERIFIED_DB.get(payload.company_name, {}).get("email", "support@company.com")
        return {"draft": response.choices[0].message.content.strip(), "target_email": target_email}
    except Exception as e:
        logger.error(f"Draft error: {str(e)}")
        raise HTTPException(status_code=500, detail="Engine overloaded. Please try again.")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SYSTEM 1 & 6: DASHBOARD & TRACKER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@app.get("/api/dashboard")
async def get_dashboard_stats():
    return SYSTEM_METRICS

@app.post("/api/report-outcome")
@limiter.limit("3/minute") 
async def report_outcome(request: Request, payload: OutcomeRequest):
    SYSTEM_METRICS["total_recovered"] += payload.amount_recovered
    SYSTEM_METRICS["cases_won"] += 1
    return {"status": "success", "message": "Community scoreboard updated!", "new_total": SYSTEM_METRICS["total_recovered"]}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SYSTEM 2: SMART TIMELINE 
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@app.get("/api/timeline/{company_name}")
async def get_deadlines(company_name: str):
    today = datetime.now()
    if company_name not in VERIFIED_DB:
        return {
            "level_1_deadline": (today + timedelta(days=7)).strftime("%Y-%m-%d"),
            "consumer_court_date": (today + timedelta(days=30)).strftime("%Y-%m-%d"),
            "warning": "Generic Company Detected: If no refund by Day 30, generate e-Daakhil package under the Consumer Protection Act."
        }
    
    reg = VERIFIED_DB[company_name]["regulator"]
    if reg == "RBI":
        return {
            "level_1_deadline": (today + timedelta(days=10)).strftime("%Y-%m-%d"),
            "ombudsman_escalation_date": (today + timedelta(days=30)).strftime("%Y-%m-%d"),
            "warning": "Banking Rule: If no refund by Day 30, file at cms.rbi.org.in"
        }
    else:
        return {
            "level_1_deadline": (today + timedelta(days=7)).strftime("%Y-%m-%d"),
            "consumer_court_date": (today + timedelta(days=30)).strftime("%Y-%m-%d"),
            "warning": "CCPA Rule: If no refund by Day 30, file via e-Daakhil."
        }

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SYSTEM 3: KARMA AI CHATBOT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@app.post("/api/chat")
@limiter.limit("10/minute")
async def karma_chat(request: Request, payload: ChatRequest):
    try:
        response = await client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "You are Karma AI. Give sharp, 2-sentence legal pushbacks to corporate delays using RBI/CCPA rules."},
                {"role": "user", "content": payload.user_message}
            ],
            temperature=0.4, max_tokens=300
        )
        return {"reply": response.choices[0].message.content.strip()}
    except Exception:
        raise HTTPException(status_code=500, detail="Karma AI is busy.")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SYSTEM 4: E-FILING PACKAGE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@app.post("/api/edakhil-package")
@limiter.limit("5/minute") 
async def generate_edakhil(request: Request, payload: DisputeRequest):
    target_email = VERIFIED_DB.get(payload.company_name, {}).get("email", "Find company email online")
    edakhil_json = {
        "Complainant_Details": {"Name": payload.user_name, "Mobile": payload.user_phone, "Email": payload.user_email},
        "Opposite_Party": {"Name": payload.company_name, "Email": target_email},
        "Grievance_Details": {"Dispute_Value": payload.disputed_amount, "Transaction_ID": payload.order_id},
        "Prayer_for_Relief": f"Immediate refund of ₹{payload.disputed_amount} plus 12% interest for mental agony caused by deficiency in service."
    }
    return {"status": "Package Generated", "data": edakhil_json, "next_step": "Upload this structure directly to edaakhil.nic.in"}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SYSTEM 5: BULLSHIT DETECTOR
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@app.post("/api/detect-bs")
@limiter.limit("5/minute")
async def detect_bullshit(request: Request, payload: BSDetectorRequest):
    try:
        response = await client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "Analyze the corporate email. State if they are using a 'Stalling Tactic', 'Illegal Demand', or 'Valid Request'. Explain why in 1 sentence. Then give the user 1 sentence to reply with."},
                {"role": "user", "content": f"Corporate Email: {payload.corporate_reply}"}
            ],
            temperature=0.1, max_tokens=200
        )
        return {"analysis": response.choices[0].message.content.strip()}
    except Exception:
        raise HTTPException(status_code=500, detail="Detector offline.")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SYSTEM 7: MULTI-CHANNEL MATRIX 
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@app.get("/api/matrix/{company_name}")
async def escalation_matrix(company_name: str):
    if company_name not in VERIFIED_DB:
        return {
            "company": company_name,
            "step_1_email": "Find general support email online",
            "step_2_social_pressure": f"Search Twitter/X for @{company_name.replace(' ', '')} and post your generated notice.",
            "step_3_portal": "File on the National Consumer Helpline (NCH) app."
        }
    
    data = VERIFIED_DB[company_name]
    return {
        "company": company_name,
        "step_1_email": data["email"],
        "step_2_social_pressure": f"Tweet at {data.get('twitter', 'their handle')} using #KarmaClaims",
        "step_3_portal": data.get('portal', 'No portal found')
    }