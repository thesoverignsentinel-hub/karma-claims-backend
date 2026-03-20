import os
import logging
import httpx
import traceback
import asyncio
import time
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, field_validator, EmailStr
from dotenv import load_dotenv
from groq import AsyncGroq
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from supabase import create_client, Client

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ⚡ KARMA CLAIMS — JUGGERNAUT ENGINE v6.0
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")
logger = logging.getLogger("karma-claims")

load_dotenv()
API_KEY = os.getenv("GROQ_API_KEY")
if not API_KEY:
    raise RuntimeError("[FATAL] GROQ_API_KEY is not set.")

HF_TOKEN = os.getenv("HF_TOKEN")
if not HF_TOKEN:
    logger.warning("[WARNING] HF_TOKEN is not set. Embedding features will use zero vectors as fallback.")

# Reverting to wildcard for local development so your frontend doesn't get blocked
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🗄️ SUPABASE SECTOR ROUTING MAP (The Universal Translator)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTOR_METADATA_MAP = {
    # 1. Inputs coming from the Home Page Grid (Perfectly matched to your upload script)
    "E-Commerce": "E-Commerce",
    "Quick Commerce": "E-Commerce",
    "Food Delivery": "E-Commerce",
    "Subscriptions & Apps": "E-Commerce",
    "Banking & UPI": "Banking & Fintech",
    "Stock Brokers": "Wealth-Tech",
    "Loan Apps & CIBIL": "Credit Bureaus",
    "Health Insurance": "Insurance",
    "Airlines & IRCTC": "Airlines & Travel",
    "Couriers & Parcels": "Logistics & Couriers",
    "Automobiles & EV": "Automobiles",
    "EdTech & Coaching": "EdTech",
    "Real Estate": "Real Estate",
    "Telecom & WiFi": "Telecom",
    "Electricity Boards": "Utilities",
    "Banking & Fintech": "Banking & Fintech",
    "Wealth-Tech & Brokers": "Wealth-Tech",
    "Airlines & Travel": "Airlines & Travel",
    "Logistics & Couriers": "Logistics & Couriers",
    "Electricity & Utilities": "Utilities",
    
    # 2. Inputs coming from the Dashboard Auto-Complete Database
    "Banking": "Banking & Fintech",
    "Fintech": "Banking & Fintech",
    "Wealth-Tech": "Wealth-Tech",
    "Loans & Credit": "Credit Bureaus",
    "Credit Bureaus": "Credit Bureaus",
    "Airlines": "Airlines & Travel",
    "Travel": "Airlines & Travel",
    "Mobility": "Airlines & Travel", 
    "EdTech": "EdTech",
    "Health Insurance": "Insurance",
    "Insurance": "Insurance",
    "Automobiles": "Automobiles",
    "Logistics": "Logistics & Couriers",
    "Telecom": "Telecom",
    "Utilities": "Utilities",
    "Digital Subscriptions": "E-Commerce",
    "Subscriptions & Apps": "E-Commerce",
    "Automobiles & EV": "Automobiles",
    "EdTech & Coaching": "EdTech",
    "Telecom & WiFi": "Telecom",
    "Loan Apps & CIBIL": "Credit Bureaus",
    "Credit Bureaus": "Credit Bureaus",
    "Logistics & Couriers": "Logistics & Couriers",
    "Couriers & Parcels": "Logistics & Couriers",
    "Medical & Hospitals": "General",
    "General": "General"
}

# --- SUPABASE DB INITIALIZATION ---
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
supabase: Client | None = None
supabase_admin: Client | None = None
if SUPABASE_URL and SUPABASE_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    logger.info("Supabase Data Connection: ACTIVE")
else:
    logger.warning("Supabase Data Connection: INACTIVE (Missing Keys)")
if SUPABASE_URL and SUPABASE_SERVICE_KEY:
    supabase_admin = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    logger.info("Supabase Admin (Vault Access): ACTIVE")
else:
    logger.warning("Supabase Admin: INACTIVE — RAG vault search will be limited")

# ── 1. THE LIVING SCOREBOARD ──
def get_dynamic_metrics():
    db_recovered = 0.0
    db_wins = 0
    if supabase:
        try:
            # 🛡️ OOM PATCH: Limit the query payload so the server doesn't crash on viral scale
            wins_res = supabase.table('karma_precedents').select('amount_recovered', count='exact').order('id', desc=True).limit(1000).execute()
            if wins_res.data:
                db_wins = wins_res.count or 0
                db_recovered = sum(row.get('amount_recovered', 0) for row in wins_res.data)
                
                # Extrapolate for massive scale if count > 1000
                if db_wins > 1000 and len(wins_res.data) > 0:
                    avg_recovery = db_recovered / len(wins_res.data)
                    db_recovered = avg_recovery * db_wins
        except Exception:
            pass
    return {
        "total_recovered": db_recovered,
        "cases_won": db_wins,
        "active_users": db_wins + 5  # Baseline network activity
    }


import json

# ── 2. THE VERIFIED DB (Loaded dynamically from corporate_db.json) ──
try:
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'corporate_db.json')
    with open(db_path, 'r') as db_file:
        VERIFIED_DB = json.load(db_file)
    logger.info(f"Loaded {len(VERIFIED_DB)} companies into the Juggernaut Engine.")
except FileNotFoundError:
    logger.warning("corporate_db.json not found. Running with empty corporate database.")
    VERIFIED_DB = {}
# ── 3. RATE LIMITER & APP SETUP ──
def get_real_ip(request: Request):
    # 🛡️ PROXY PATCH: Extract real user IP behind cloud load balancers
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"

limiter = Limiter(key_func=get_real_ip)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("⚡ Karma Claims Juggernaut Engine V6 is online.")
    yield

app = FastAPI(title="Karma Claims v6.0", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(CORSMiddleware, allow_origins=ALLOWED_ORIGINS, allow_credentials=False, allow_methods=["*"], allow_headers=["*"])

client = AsyncGroq(api_key=API_KEY)

# 🛡️ INFRASTRUCTURE PATCH: Prevent Render OOM Crashes by capping concurrent heavy AI tasks
MAX_CONCURRENT_WAR_ROOMS = 3
war_room_semaphore = asyncio.Semaphore(MAX_CONCURRENT_WAR_ROOMS)

# --- NEW: SAAS AUTHENTICATION MIDDLEWARE ---
security_bearer = HTTPBearer(auto_error=False)

async def get_optional_user(credentials: HTTPAuthorizationCredentials | None = Depends(security_bearer)):
    """Allows anonymous users (Front Door) but secures state for logged-in users."""
    if not credentials or not supabase:
        return None
    try:
        user_res = supabase.auth.get_user(credentials.credentials)
        return user_res.user if user_res else None
    except Exception:
        return None

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer())):
    """Strictly requires a logged-in user to access private history/sessions."""
    token = credentials.credentials
    if not supabase:
        raise HTTPException(status_code=500, detail="Database connection inactive.")
    try:
        user_res = supabase.auth.get_user(token)
        if not user_res or not user_res.user:
            raise HTTPException(status_code=401, detail="Invalid token")
        return user_res.user
    except Exception:
        raise HTTPException(status_code=401, detail="Could not validate credentials")


# ── 4. BOT PROTECTION & VALIDATION ──
_INJECTION_PATTERNS = [
    "ignore above", "ignore previous", "disregard", "system:",
    "<|", "|>", "prompt:", "assistant:",
    "override", "jailbreak", "forget instructions",
]



class TriageMessage(BaseModel): role: str; content: str

class TriageRequest(BaseModel):
    user_message: str
    chat_history: list[TriageMessage] = []
    image_base64: str | None = None  

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel): 
    user_message: str
    company_name: str = "Unknown Sector" 
    session_id: str | None = None 
    image_base64: str | None = None
    evidence_images: list[str] = []  # Multiple base64 images from Evidence Locker
    sector: str = "General"
    history: list[ChatMessage] = []

class EvidenceLockerRequest(BaseModel):
    session_id: str
    file_name: str
    file_base64: str  # base64 data URL

class OutcomeRequest(BaseModel): 
    amount_recovered: float
    company_name: str
    case_description: str = "Recovered funds successfully." 
    has_screenshot: bool = False

    # 🛡️ INTEGRITY PATCH: Cap claims at 50 Lakhs (District Commission limit) to prevent troll manipulation
    @field_validator('amount_recovered')
    @classmethod
    def validate_amount(cls, v):
        if v < 0 or v > 5000000:
            raise ValueError("Amount exceeds District Commission jurisdiction or is invalid.")
        return v

class EdakhilRequest(BaseModel):
    session_id: str
    user_name: str
    user_address: str
    company_name: str

# --- NEW: PYDANTIC MODELS FOR V6 ---
class CorrectionRequest(BaseModel):
    sector: str
    faulty_claim: str
    corrected_fact: str

class BSDetectorRequest(BaseModel): 
    corporate_reply: str



# ── 6. ENDPOINTS ──

@app.get("/health")
async def health_check():
    return {"status": "Live", "version": "6.0", "systems_online": 10}

@app.get("/")
@app.head("/")
async def root():
    return {"message": "Karma Claims API Engine V6 is online and operational."}

# --- NEW: API BRIDGE FOR THE 500-COMPANY FRONTEND SEARCH ---
@app.get("/api/companies")
async def get_company_list():
    """Feeds the 500-Company list to the Frontend Autocomplete Search Bar"""
    formatted_list = [{
        "name": name,
        "sector": data["industry"],
        "twitter": data.get("twitter", ""),
        "ceo_name": data.get("ceo_name", ""),
        "nodal_email": data.get("nodal_email", ""),
        "appellate_email": data.get("appellate_email", ""),
        "nuclear_tier": data.get("nuclear_tier", "standard")
    } for name, data in VERIFIED_DB.items()]
    return {"companies": formatted_list}

# --- NEW V6: AI AUDITOR (Daily Learning) ---
@app.post("/api/audit-correction")
@limiter.limit("2/minute")
async def audit_correction(request: Request, payload: CorrectionRequest, user = Depends(get_current_user)):
    if not supabase: raise HTTPException(status_code=500, detail="Database connection inactive.")
    
    audit_prompt = f"""
    SECTOR: {payload.sector}
    USER CLAIM: "{payload.faulty_claim}"
    PROPOSED CORRECTION: "{payload.corrected_fact}"
    
    Analyze if the PROPOSED CORRECTION is a legally and factually accurate statement regarding Indian corporate or consumer law. 
    Reply strictly with 'VALID' if it is a real rule/update, or 'INVALID' followed by a short reason if it is false.
    """
    try:
        response = await client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": audit_prompt}],
            temperature=0.1
        )
        audit_result = response.choices[0].message.content.strip()
        
        if audit_result.upper().startswith("VALID"):
            supabase.table('realtime_patches').insert({
                "sector": payload.sector,
                "faulty_claim": payload.faulty_claim,
                "corrected_fact": payload.corrected_fact,
                "verified_by_auditor": True,
                "source_user_id": user.id
            }).execute()
            return {"status": "success", "message": "Juggernaut memory patched successfully. The Sentinel is now smarter."}
        
        return {"status": "failed", "reason": audit_result}
    except Exception as e:
        logger.error(f"Auditor failed: {e}")
        raise HTTPException(status_code=500, detail="Auditor offline.")

# --- NEW V6: STALLING DETECTOR ---
@app.post("/api/detect-bs")
@limiter.limit("5/minute")
async def detect_bs(request: Request, payload: BSDetectorRequest):
    prompt = f"""You are the Sovereign Sentinel — an elite Indian consumer law expert and corporate bullshit detector.

A consumer has received this reply from a company:
---
{payload.corporate_reply}
---

Analyze it with surgical precision. Respond ONLY in this exact JSON format, nothing else:

{{
  "verdict": "STALLING TACTIC" | "ILLEGAL DEMAND" | "VALID RESPONSE" | "PARTIAL COMPLIANCE",
  "verdict_reason": "One sharp sentence explaining the verdict.",
  "tactics_detected": ["Tactic 1", "Tactic 2"],
  "law_violations": ["Violated law or rule with section number, or empty string if none"],
  "their_hidden_agenda": "What they are really trying to do in plain language.",
  "your_power_move": "Exact counter-action the consumer should take right now — be specific.",
  "counter_response": "A sharp 3-sentence reply the consumer can send back immediately. Professional but lethal."
}}

Be brutally honest. Name the exact Indian law or RBI/TRAI/IRDAI regulation they are violating if applicable. No fluff."""

    try:
        response = await client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1, max_tokens=800
        )
        raw = response.choices[0].message.content.strip()
        import json as _json
        import re
        
        # 🛡️ BULLETPROOF JSON EXTRACTION: Find the first { and last }
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if not match:
            raise ValueError("No JSON object found in response.")
        
        clean_json = match.group(0)
        parsed = _json.loads(clean_json)
        return {"analysis": parsed, "raw": raw}
    except Exception as e:
        logger.error(f"BS Detector failed: {e}")
        raise HTTPException(status_code=500, detail="Detector offline.")



@app.get("/api/dashboard")
async def get_dashboard_stats():
    return get_dynamic_metrics()

class StatusUpdateRequest(BaseModel):
    session_id: str
    status: str  # "drafted" | "dispatched" | "escalated" | "won"
    amount_recovered: float = 0.0

@app.post("/api/evidence/add")
@limiter.limit("20/minute")
async def add_evidence(request: Request, payload: EvidenceLockerRequest, user = Depends(get_current_user)):
    """Adds a piece of evidence to a case and runs Vision AI analysis on it."""
    if not supabase:
        raise HTTPException(status_code=500, detail="Database offline.")
    try:
        # Security: verify ownership
        session_res = supabase.table('chat_sessions').select('user_id, evidence_files').eq('id', payload.session_id).execute()
        if not session_res.data or session_res.data[0]['user_id'] != user.id:
            raise HTTPException(status_code=403, detail="Unauthorized.")

        # Run Vision AI analysis on the uploaded image
        analysis_text = "Evidence uploaded successfully."
        try:
            vision_response = await client.chat.completions.create(
                model="llama-3.2-11b-vision-preview",
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": """You are a legal evidence analyst. Analyze this screenshot/image submitted as evidence in an Indian consumer dispute.
                            In 2-3 sentences, describe:
                            1. What this image shows (order confirmation, chat screenshot, invoice, defective product, etc.)
                            2. What specific fact it proves that helps the consumer's case.
                            Be precise and factual. No opinions."""
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": payload.file_base64}
                        }
                    ]
                }],
                temperature=0.1,
                max_tokens=200
            )
            analysis_text = vision_response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Vision analysis failed for evidence: {e}")
            analysis_text = "Image uploaded. Manual review required."

        # Append to existing evidence array
        existing_evidence = session_res.data[0].get('evidence_files') or []
        import random
        # 🛡️ ID COLLISION PATCH: Ensure batch uploads get strictly unique IDs
        new_item = {
            "id": f"ev_{int(time.time() * 1000)}_{random.randint(1000, 9999)}",
            "name": payload.file_name,
            "base64": "Removed for DB optimization - stored locally",
            "analysis": analysis_text,
            "uploaded_at": time.strftime("%Y-%m-%d %H:%M")
        }
        existing_evidence.append(new_item)

        # Cap at 10 evidence items per case
        if len(existing_evidence) > 10:
            existing_evidence = existing_evidence[-10:]

        supabase.table('chat_sessions').update(
            {"evidence_files": existing_evidence}
        ).eq('id', payload.session_id).execute()

        # 🛡️ CHAT SYNC PATCH: Write the upload event into the chat history so it survives page refreshes!
        supabase.table('messages').insert({
            "session_id": payload.session_id, 
            "role": "user", 
            "content": f"📷 [Evidence Uploaded: {payload.file_name}]\nAnalysis: {analysis_text}"
        }).execute()

        return {
            "status": "success",
            "analysis": analysis_text,
            "evidence_count": len(existing_evidence),
            "evidence_id": new_item["id"]
        }
    except HTTPException: raise
    except Exception as e:
        logger.error(f"Evidence upload failed: {e}")
        raise HTTPException(status_code=500, detail="Evidence upload failed.")


@app.get("/api/evidence/{session_id}")
@limiter.limit("20/minute")
async def get_evidence(request: Request, session_id: str, user = Depends(get_current_user)):
    """Retrieves all evidence for a case."""
    if not supabase:
        raise HTTPException(status_code=500, detail="Database offline.")
    try:
        session_res = supabase.table('chat_sessions').select('user_id, evidence_files').eq('id', session_id).execute()
        if not session_res.data or session_res.data[0]['user_id'] != user.id:
            raise HTTPException(status_code=403, detail="Unauthorized.")
        
        evidence = session_res.data[0].get('evidence_files') or []
        # Strip base64 from list response to keep payload small — only send name, analysis, id
        safe_evidence = [{"id": e["id"], "name": e["name"], "analysis": e["analysis"], "uploaded_at": e.get("uploaded_at", "")} for e in evidence]
        return {"status": "success", "evidence": safe_evidence, "count": len(safe_evidence)}
    except HTTPException: raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to retrieve evidence.")


@app.delete("/api/evidence/{session_id}/{evidence_id}")
@limiter.limit("20/minute")
async def delete_evidence(request: Request, session_id: str, evidence_id: str, user = Depends(get_current_user)):
    """Deletes a single evidence item from a case."""
    if not supabase:
        raise HTTPException(status_code=500, detail="Database offline.")
    try:
        session_res = supabase.table('chat_sessions').select('user_id, evidence_files').eq('id', session_id).execute()
        if not session_res.data or session_res.data[0]['user_id'] != user.id:
            raise HTTPException(status_code=403, detail="Unauthorized.")

        evidence = session_res.data[0].get('evidence_files') or []
        updated = [e for e in evidence if e["id"] != evidence_id]
        supabase.table('chat_sessions').update({"evidence_files": updated}).eq('id', session_id).execute()
        return {"status": "success", "evidence_count": len(updated)}
    except HTTPException: raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to delete evidence.")
    
@app.post("/api/update-case-status")
@limiter.limit("10/minute")
async def update_case_status(request: Request, payload: StatusUpdateRequest, user = Depends(get_current_user)):
    """Allows user to update the live status of their case."""
    valid_statuses = ["drafted", "dispatched", "escalated", "won"]
    if payload.status not in valid_statuses:
        raise HTTPException(status_code=400, detail="Invalid status.")
    if not supabase:
        raise HTTPException(status_code=500, detail="Database offline.")
    try:
        # Security: verify ownership before updating
        session_res = supabase.table('chat_sessions').select('user_id').eq('id', payload.session_id).execute()
        if not session_res.data or session_res.data[0]['user_id'] != user.id:
            raise HTTPException(status_code=403, detail="Unauthorized.")
        
        update_data = {"status": payload.status}
        if payload.status == "won" and payload.amount_recovered > 0:
            update_data["amount_recovered"] = payload.amount_recovered

        supabase.table('chat_sessions').update(update_data).eq('id', payload.session_id).execute()
        return {"status": "success", "message": f"Case status updated to '{payload.status}'."}
    except HTTPException: raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to update case status.")

@app.post("/api/report-outcome")
@limiter.limit("3/minute") 
async def report_outcome(request: Request, payload: OutcomeRequest, user = Depends(get_current_user)):
    if supabase:
        try:
            hf_api_url = "https://router.huggingface.co/hf-inference/models/sentence-transformers/all-MiniLM-L6-v2/pipeline/feature-extraction"
            headers = {"Authorization": f"Bearer {os.getenv('HF_TOKEN')}"}
            # 🛡️ MATH PATCH: Use microscopic non-zero values to prevent PostgreSQL Division-by-Zero NaN crashes
            query_vector = [0.0001] * 384
            
            async with httpx.AsyncClient(timeout=60.0) as http_client:
                hf_response = await http_client.post(hf_api_url, headers=headers, json={"inputs": payload.case_description})
                if hf_response.status_code == 200:
                    res_json = hf_response.json()
                    # 🛡️ ANTI-CRASH PATCH: Safely handle HF cold-start dictionary errors
                    if isinstance(res_json, list) and len(res_json) > 0:
                        query_vector = res_json[0] if isinstance(res_json[0], list) else res_json
                    elif isinstance(res_json, dict) and "error" in res_json:
                        logger.warning(f"HF Model Cold Start in report_outcome: {res_json.get('error')}")
                        # query_vector gracefully defaults to the [0.0] * 384 fallback defined above
            
            supabase.table('karma_precedents').insert({
                "company_name": payload.company_name,
                "case_description": payload.case_description,
                "amount_recovered": payload.amount_recovered,
                "legal_strategy_used": "Automated Legal Notice / AI War Room",
                "embedding": query_vector
            }).execute()
        except Exception as e:
            logger.error(f"Failed to save precedent: {str(e)}")

    return {"status": "success", "new_total": get_dynamic_metrics()["total_recovered"]}

@app.get("/api/timeline/{company_name}")
async def get_deadlines(company_name: str):
    from datetime import timezone
    # 🛡️ TIMEZONE PATCH: Force Indian Standard Time (IST) so midnight roll-overs don't break legal deadlines on UTC cloud servers
    today = datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)
    
    # 🛡️ URL INTEGRITY PATCH: Ensure case-insensitive matching for URL parameters
    matched_company = company_name
    for db_key in VERIFIED_DB.keys():
        if db_key.lower() == company_name.lower():
            matched_company = db_key
            break

    if matched_company not in VERIFIED_DB:
        return {
            "level_1_deadline": (today + timedelta(days=7)).strftime("%Y-%m-%d"),
            "consumer_court_date": (today + timedelta(days=30)).strftime("%Y-%m-%d"),
            "warning": "Generic Company Detected: If no refund by Day 30, generate e-Daakhil package.",
            "unverified": True
        }
    reg = VERIFIED_DB[matched_company]["regulator"]
    if reg == "RBI":
        return {
            "level_1_deadline": (today + timedelta(days=10)).strftime("%Y-%m-%d"),
            "ombudsman_escalation_date": (today + timedelta(days=30)).strftime("%Y-%m-%d"),
            "warning": "Banking Rule: If no refund by Day 30, file at cms.rbi.org.in",
            "unverified": False
        }
    else:
        return {
            "level_1_deadline": (today + timedelta(days=7)).strftime("%Y-%m-%d"),
            "consumer_court_date": (today + timedelta(days=30)).strftime("%Y-%m-%d"),
            "warning": f"{reg} Rule: If no refund by Day 30, file via e-Daakhil or respective portal.",
            "unverified": False
        }

@app.post("/api/triage-chat")
@limiter.limit("10/minute")
async def triage_copilot(request: Request, payload: TriageRequest):
    try:
        system_prompt = """
        You are the Intake Paralegal for Karma Claims. Extract 4 variables from the user's story or screenshot.
        REQUIRED: 1. Company Name 2. User's Full Name 3. Disputed Amount 4. Order ID / PNR
        If missing, strictly ask. If all 4 are provided, reply EXACTLY:
        [READY_FOR_DRAFT] | {"company_name": "X", "user_name": "Y", "disputed_amount": "Z", "order_id": "W"}
        """
        messages = [{"role": "system", "content": system_prompt}]
        for msg in payload.chat_history: messages.append({"role": msg.role, "content": msg.content})

        if payload.image_base64:
            messages.append({"role": "user", "content": [
                {"type": "text", "text": payload.user_message or "Analyze this screenshot."},
                {"type": "image_url", "image_url": {"url": payload.image_base64}}
            ]})
            active_model = "llama-3.2-11b-vision-preview"
        else:
            messages.append({"role": "user", "content": payload.user_message})
            active_model = "llama-3.3-70b-versatile"

        response = await client.chat.completions.create(model=active_model, messages=messages, temperature=0.1, max_tokens=400)
        bot_reply = response.choices[0].message.content

        if "[READY_FOR_DRAFT]" in bot_reply:
            # 🛡️ PARSING PATCH: Safely extract JSON even if the AI forgets the delimiter
            import re
            match = re.search(r'\{.*\}', bot_reply, re.DOTALL)
            json_str = match.group(0) if match else "{}"
            return {"status": "complete", "reply": "All details secured. Compiling notice...", "extracted_data": json_str}
        return {"status": "asking", "reply": bot_reply}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Intake Copilot offline.")

# --- THE JUGGERNAUT ENGINE CHAT ENDPOINT (UPGRADED CONVERSATIONAL AI) ---
@app.post("/api/chat")
@limiter.limit("10/minute")
async def karma_chat(request: Request, payload: ChatRequest, user = Depends(get_optional_user)):
    try:
        # 🛡️ THE SECURITY PATCH: Catch injections before they hit the LLM
        v_lower = payload.user_message.lower()
        for pattern in _INJECTION_PATTERNS:
            if pattern in v_lower:
                return {"reply": "🛑 SECURITY ALERT: The Sentinel has detected unauthorized override commands. Access denied."}

        session_id = payload.session_id
        chat_history_text = ""
        
        # --- 1. SAAS STATE MANAGEMENT & MEMORY ---
        db_display_name = payload.company_name
        if not db_display_name or db_display_name == "Unknown Sector" or db_display_name == "General":
            db_display_name = payload.sector

        if user and supabase:
            if not session_id:
                # New Case: Save to DB, but use the frontend's history for context
                session_res = supabase.table('chat_sessions').insert({
                    "user_id": user.id, "company_name": db_display_name, "issue_summary": payload.user_message[:50] + "..."
                }).execute()
                session_id = session_res.data[0]['id']
                
                # 🛡️ GUEST-SYNC PATCH: Bulk insert the previous guest history into the DB so it is permanently saved!
                bulk_messages = []
                for msg in payload.history:
                    chat_history_text += f"{msg.role.upper()}: {msg.content}\n"
                    bulk_messages.append({"session_id": session_id, "role": msg.role, "content": msg.content})
                
                if bulk_messages:
                    supabase.table('messages').insert(bulk_messages).execute()
            else:
                # 🛡️ SECURITY PATCH: Verify case ownership before loading history into the AI's brain
                auth_check = supabase.table('chat_sessions').select('user_id').eq('id', session_id).execute()
                if not auth_check.data or auth_check.data[0]['user_id'] != user.id:
                    return {"reply": "🛑 SECURITY ALERT: Unauthorized case access detected. Session terminated."}

                # Existing Case: STRICTLY rely on DB memory to prevent duplication
                past_messages = supabase.table('messages').select('role, content').eq('session_id', session_id).order('created_at', desc=False).execute()
                if past_messages.data:
                    # 🛡️ TOKEN OPTIMIZATION: Keep only the last 6 interactions to prevent context limits
                    recent_messages = past_messages.data[-6:]
                    for msg in recent_messages:
                        chat_history_text += f"{msg['role'].upper()}: {msg['content']}\n"
                
                # 🛡️ EVIDENCE LINK PATCH: Feed the locked evidence facts to the AI
                session_meta = supabase.table('chat_sessions').select('evidence_files').eq('id', session_id).execute()
                if session_meta.data and session_meta.data[0].get('evidence_files'):
                    chat_history_text += "\n[SYSTEM NOTE: USER UPLOADED THE FOLLOWING EVIDENCE TO THEIR LOCKER]\n"
                    for ev in session_meta.data[0]['evidence_files']:
                        chat_history_text += f"- Evidence Document '{ev['name']}': {ev['analysis']}\n"
            
            supabase.table('messages').insert({"session_id": session_id, "role": "user", "content": payload.user_message}).execute()
        else:
            # --- 0. GUEST MEMORY FALLBACK ---
            for msg in payload.history:
                chat_history_text += f"{msg.role.upper()}: {msg.content}\n"

        # --- 2. DYNAMIC SECTOR-SPECIFIC INTELLIGENCE ROUTER ---
        user_sector = payload.sector 
        # Make matching bulletproof (case-insensitive, strips hidden spaces)
        sector_map_lower = {k.lower().strip(): v for k, v in SECTOR_METADATA_MAP.items()}
        safe_sector = user_sector.lower().strip()
        
        # Route to Master Category (Ensures "Airlines" perfectly connects to Supabase)
        ai_master_category = sector_map_lower.get(safe_sector, "General")

        # We hardcode the exact corporate BS and legal counters for each master sector to prevent hallucinations.
        SECTOR_INTELLIGENCE = {
            "Banking & Fintech": """
            - SPECIFIC FACTS NEEDED: Bank/App Name, Transaction ID (UTR), Amount, Date.
            - COMMON CORPORATE BS: "We are just a technology service provider (TSP) / UPI facilitator. Contact the merchant."
            - YOUR LEGAL COUNTER: This is a lie. Under NPCI guidelines and RBI's Digital Fraud Framework, the payment app (e.g., Google Pay/PhonePe) holds joint liability for failed/disputed UPI transactions.
            """,
            "E-Commerce": """
            - SPECIFIC FACTS NEEDED: Platform Name, Order ID, Amount, Defect/Issue.
            - COMMON CORPORATE BS: "We are just an intermediary marketplace. We don't make the product. Contact the seller/restaurant."
            - YOUR LEGAL COUNTER: This is invalid. Under Rule 5 and Rule 11 of the Consumer Protection (E-Commerce) Rules 2020, the platform is liable for 'fallback liability' if the seller fails to deliver or refund.
            """,
            "Airlines & Travel": """
            - SPECIFIC FACTS NEEDED: Airline/Portal Name, PNR Number, Date, Issue.
            - COMMON CORPORATE BS: "The delay was due to bad weather/ATC (Force Majeure), so no compensation is owed."
            - YOUR LEGAL COUNTER: Do not accept this blindly. Under DGCA CAR Section 3, Series M, they must provide verifiable METAR reports. Threaten AirSewa escalation.
            """,
            "Insurance": """
            - SPECIFIC FACTS NEEDED: Insurer Name, Policy Number, Claim ID, Rejection Reason.
            - COMMON CORPORATE BS: "Rejected due to non-disclosure of pre-existing condition."
            - YOUR LEGAL COUNTER: If the policy is older than 36 months, invoke the IRDAI 3-Year Moratorium rule. If it's newer, attack their 'Burden of Proof'.
            """,
            "EdTech": """
            - SPECIFIC FACTS NEEDED: EdTech Company, Course Name, Amount paid, Loan partner (if any).
            - COMMON CORPORATE BS: "No refund policy. You already logged into the portal."
            - YOUR LEGAL COUNTER: 'No Refund' policies are illegal Unfair Contracts under Section 2(46) of the Consumer Protection Act, 2019.
            """,
            "Digital Subscriptions": """
            - SPECIFIC FACTS NEEDED: App/Platform Name, Subscription Amount, Date of auto-debit, Cancellation attempt proof.
            - COMMON CORPORATE BS: "Cancellation was not processed in time. Our policy states no refund after billing cycle starts."
            - YOUR LEGAL COUNTER: Auto-renewal without explicit informed consent violates Rule 5 of the Consumer Protection (E-Commerce) Rules 2020 and RBI's e-Mandate guidelines requiring a pre-debit notification 24 hours before charge.
            """,
            "Wealth-Tech": """
            - SPECIFIC FACTS NEEDED: Broker/App Name, Client ID, Trade ID, Amount lost, Date of failure.
            - COMMON CORPORATE BS: "Market volatility caused the issue. We are not responsible for losses due to technical delays."
            - YOUR LEGAL COUNTER: This is false. Under SEBI Circular SEBI/HO/MIRSD, brokers are liable for platform-side order execution failures. Technical failures that cause financial loss are a clear Deficiency in Service under CPA 2019.
            """,
            "Credit Bureaus": """
            - SPECIFIC FACTS NEEDED: Bureau Name (CIBIL/Experian), Loan App Name, Incorrect entry detail, Date of dispute filed.
            - COMMON CORPORATE BS: "We only report what lenders give us. Contact your bank to correct the error."
            - YOUR LEGAL COUNTER: Under RBI's Credit Information Companies (Regulation) Act 2005, the bureau has a legal obligation to investigate and correct disputes within 30 days. Shifting responsibility to lenders is illegal stonewalling.
            """,
            "Logistics & Couriers": """
            - SPECIFIC FACTS NEEDED: Courier Company, AWB/Tracking Number, Package value, Last tracking status, Date.
            - COMMON CORPORATE BS: "The package was marked delivered. We cannot take responsibility after delivery confirmation."
            - YOUR LEGAL COUNTER: A GPS ping or a photo of a doorstep is NOT proof of delivery to the correct person. Under Section 2(11) of CPA 2019, this constitutes Deficiency in Service. Demand their 'Proof of Delivery' document with recipient signature.
            """,
            "Automobiles": """
            - SPECIFIC FACTS NEEDED: Car Brand, Model, VIN/Registration, Dealer Name, Defect description, Service dates.
            - COMMON CORPORATE BS: "The defect is due to owner misuse and is not covered under warranty."
            - YOUR LEGAL COUNTER: The burden of proof for 'misuse' lies with the manufacturer, not the consumer. Under the Consumer Protection Act 2019, a manufacturing defect reported within the warranty period triggers mandatory repair, replacement, or refund under Section 2(9).
            """,
            "Real Estate": """
            - SPECIFIC FACTS NEEDED: Builder Name, Project Name, RERA Registration Number, Agreement Date, Promised vs Actual possession date.
            - COMMON CORPORATE BS: "Delays are due to force majeure / COVID / government approvals beyond our control."
            - YOUR LEGAL COUNTER: Under Section 18 of the Real Estate (Regulation and Development) Act 2016, the builder is liable to pay interest at SBI's Marginal Cost Lending Rate for every month of delay, regardless of the reason cited, unless the allottee caused the delay.
            """,
            "Telecom": """
            - SPECIFIC FACTS NEEDED: Operator Name, Mobile Number, Service type (calls/data/broadband), Issue dates, Complaint reference number with operator.
            - COMMON CORPORATE BS: "The issue was due to network upgrades in your area. Service has been restored."
            - YOUR LEGAL COUNTER: Under TRAI's Quality of Service Regulations, operators must maintain minimum benchmarks. You are entitled to a bill credit for the downtime period. Escalate to the Telecom Consumer Complaint Redressal Forum (TCCRF) if unresolved in 30 days.
            """,
            "Utilities": """
            - SPECIFIC FACTS NEEDED: Electricity Board/DISCOM Name, Consumer Number, Billing period, Excess amount billed, Any meter reading anomalies.
            - COMMON CORPORATE BS: "The meter reading is correct as per our records. You must pay the bill."
            - YOUR LEGAL COUNTER: Under the Electricity Act 2003 and respective State Electricity Regulatory Commission regulations, you have the right to demand a meter accuracy test. If the meter is found faulty, all excess billing must be reversed. File with the Electricity Ombudsman if unresolved.
            """,
            "Credit Bureaus": """
            - SPECIFIC FACTS NEEDED: Bureau name (CIBIL/Experian/Equifax/CRIF High Mark), Loan account number, Lender who reported wrong data, Exact error (wrong status/outstanding amount/active after closure/wrong name).
            - COMMON CORPORATE BS: "We only report what lenders give us. Contact your bank directly to fix the error."
            - YOUR LEGAL COUNTER: This is illegal deflection. Under the Credit Information Companies (Regulation) Act 2005 Section 22 and RBI Master Direction on Credit Information (updated 2023), the bureau has a DIRECT 30-day correction obligation — independent of the lender. Both the bureau AND the lender are jointly liable. File against both simultaneously. Escalate to cms.rbi.org.in selecting Credit Information Company.
            """,
            "Logistics & Couriers": """
            - SPECIFIC FACTS NEEDED: Courier company name (Delhivery/BlueDart/DTDC/Ecom Express/India Post), AWB/tracking number, Declared value of package, Last tracking status shown, Date of expected delivery.
            - COMMON CORPORATE BS: "Our system shows delivered. We cannot accept responsibility after delivery confirmation. Contact the sender."
            - YOUR LEGAL COUNTER: A GPS ping near your address or a doorstep photo is NOT valid proof of delivery under Indian consumer law. Under CPA 2019 Section 2(11), they must produce a signed Proof of Delivery (POD) with recipient name and signature — or OTP confirmation from your registered mobile number. Demand their POD document within 48 hours. If they cannot produce it, the package is legally undelivered and they bear full liability for the declared value.
            """,
            "General": """
            - SPECIFIC FACTS NEEDED: Company name, Service paid for, Exact amount, Date of failure, What was promised vs what was delivered.
            - COMMON CORPORATE BS: "Our policy doesn't allow refunds / Please wait 48 hours / This is outside our scope / Contact the manufacturer."
            - YOUR LEGAL COUNTER: Internal corporate policies NEVER supersede the Consumer Protection Act 2019. Any contract term that creates a significant imbalance in rights is an 'Unfair Contract' under Section 2(46) CPA 2019 and is void and unenforceable. The company cannot hide behind its own unfair policies.
            """,
        }

        # Fallback for generic or unmapped sectors
        sector_knowledge = SECTOR_INTELLIGENCE.get(ai_master_category, """
            - SPECIFIC FACTS NEEDED: Company Name, Transaction/Order ID, Amount, Core Issue.
            - COMMON CORPORATE BS: Generic stalling, "Wait 48 hours", "Technical glitch", "Policy doesn't allow refunds".
            - YOUR LEGAL COUNTER: Remind the user that internal corporate policies NEVER supersede the Consumer Protection Act, 2019.
        """)

        intake_prompt = f"""You are the 'Sovereign Sentinel' for Karma AI. You are NOT a customer service rep. You are an elite, highly intelligent legal strategist and a ruthless Supreme Court litigator fighting for Indian consumers. 
        You are currently handling a case in the '{user_sector}' sector.

        CRITICAL CONTEXT (PAST CONVERSATION HISTORY):
        {chat_history_text}
        
        NEW USER MESSAGE:
        "{payload.user_message}"

        === SECTOR INTELLIGENCE FOUNDATION ===
        {sector_knowledge}
        ======================================

        YOUR COGNITIVE FRAMEWORK & INSTRUCTIONS:
        Do not over-apologize. Do not be overly chatty. Be sharp, authoritative, and tactical. Your version of empathy is taking immediate, aggressive action.

        0. RETURNING USER DETECTION:
        Check the PAST CONVERSATION HISTORY above. If the history contains a legal notice draft or the phrase "War Room", this is a RETURNING USER updating you on their case outcome.
        - DO NOT ask them for their company name or amount again. You already have it.
        - DO NOT say "Tell me what happened." Immediately acknowledge what you know: "I see your case against [company] for ₹[amount]. What happened after you sent the notice?"
        - Then listen and apply the POST-STRIKE INTELLIGENCE FRAMEWORK (Rule 5).
        - Whenever the user's history contains a company name, amount, or Order ID, refer to those specifics by name in every response. Never say "the company." Say "IndiGo" or "Razorpay" or whatever the actual name is.

        1. THE "NEW CASE" STATE:
        If this is a new issue, briefly acknowledge the wrong, then ask for the exact missing facts (Target Company, Amount, ID). Keep it to 2 sentences.

        2. THE "REVERSE UNO" PROTOCOL (CORPORATE TRAP DEFENSE):
        If the user says the company is stalling, claiming to be an "intermediary," or demanding impossible proof (like "Send a screenshot of the button not working"):
        - DO NOT say "I am writing to express my disappointment." That is weak.
        - Explain the legal trap to the user in 2 sentences. (e.g., "They are using the Burden of Proof trap. They have server logs, you don't need a screenshot.")
        - IMMEDIATE ACTION: Draft an aggressive, technical email they can copy-paste. 
        FORMAT IT EXACTLY LIKE THIS:
        
        **SUBJECT:** URGENT: Demand for Server Log Audit / RBI Violation
        **BODY:**
        I am in receipt of your unreasonable demand for a screenshot. As a technology provider, you maintain comprehensive backend server logs and API telemetry. The failure of the cancellation button on my account is recorded on your servers. 
        Under RBI guidelines, the liability to provide a functioning mandate revocation switch lies with you. I formally demand an audit of my account logs. Process my refund immediately or I will escalate to the RBI Ombudsman for deceptive trade practices.

        3. ZERO ERRORS & CONVERSATIONAL FLUIDITY:
        - NEVER output a system error. 
        - Adapt to whatever the user says, but maintain the persona of a brilliant, confident lawyer.
        - When the situation is ambiguous (e.g., user is unsure whether to settle or fight), present 2 clear options with a one-line tradeoff each before recommending.
        - Always refer to the company, amount, and Order ID by their exact names from the conversation history. Never say "the company" or "the amount" — say "Swiggy" or "₹1,249."

        4. THE WAR ROOM TRIGGER (ESCALATION):
        Whenever you draft an email, OR if the user wants to escalate to a formal multi-page Legal Notice, you MUST end your entire response with this exact phrase:
        "Shall I activate the War Room and draft the full legal strike?"

        6. RESPONSE LENGTH CALIBRATION:
        Match response length to the situation. Do not give the same length response to every message.
        - Crisis situations (company threatening, ignored notice, fear call): Full structured response with headers and action steps.
        - User asking a quick question ("what should I say?"): 2-3 bullet points max.
        - User venting or describing what happened: 1 sentence of acknowledgment, then immediately ask the one most important clarifying question.
        - Never pad a response. Every sentence must have a purpose.

        5. POST-STRIKE INTELLIGENCE FRAMEWORK — HANDLE ALL AFTER-EFFECTS:

        After the legal notice is sent, the user may return with updates. They may paste the company's exact reply directly into the chat.

        CORPORATE REPLY DETECTION — HIGHEST PRIORITY RULE:
        If the user's message contains 3 or more of these signals, treat it as a PASTED CORPORATE REPLY and activate the Reply Decoder Protocol immediately:
        - Formal salutation ("Dear", "Hi [name]", "Thank you for contacting")
        - Apology language ("We apologize", "We regret", "We are sorry")
        - Deflection phrases ("technology provider", "contact the merchant", "intermediary", "not responsible", "our policy states")
        - Stalling phrases ("under review", "48 hours", "7 working days", "escalated internally", "our team will")
        - Template closings ("Thank you for choosing", "We value your", "For further assistance")

        REPLY DECODER PROTOCOL — respond in this exact conversational structure, NO cards, NO badges, plain text like a senior advocate talking directly to the user:

        1. OPEN WITH THE VERDICT — one sharp sentence naming what they are doing.
           Example: "They are lying to you. Here is exactly how."
           Example: "This is a textbook stalling tactic. They are betting you will give up."
           Example: "This reply is illegal. Here is the exact law they are violating."

        2. EXPOSE THE LIE — explain in plain language what their response really means and why it is wrong. Name the specific Indian law, RBI/TRAI/IRDAI/NPCI circular, or court judgement they are violating. Be specific — cite section numbers and circular names, not generic references.

        3. NAME THEIR AGENDA — one sentence on what they are actually trying to do.
           Example: "They are running out your patience on a ₹499 dispute they calculate most users abandon."

        4. THE NEXT MOVE — tell the user exactly what to do right now. Not strategy. Operational instructions:
           - Exact portal URL to file at
           - Exact subject line to use
           - Exact deadline they are working with
           - Whether this unlocks a regulator escalation

        5. OFFER TO DRAFT — end with: "Want me to write that [email/complaint/counter-notice] for you right now?"

        THEN detect which scenario and layer in the specific protocol:

        SCENARIO A — NODAL OFFICER CALLS:
        Trigger phrases: "they called me", "nodal office", "got a call", "someone called from [company]"
        RESPONSE PROTOCOL:
        - Validate: "This is the Fear Call. They are scared. Here is what you do:"
        - Give these 3 rules immediately:
          1. "Say this first: 'I am recording this call for legal purposes.'"
          2. "Do NOT accept any verbal promise. Say: 'Put your complete offer in writing to [user's email] within 24 hours.'"
          3. "Do NOT reveal how far you are willing to settle. Say nothing about your bottom line."
        - Then ask: "What did they say? Tell me the exact offer amount and any conditions they mentioned."

        SCENARIO B — LOWBALL SETTLEMENT OFFER:
        Trigger phrases: "they offered", "said they'll give", "offered me", "compensation of"
        RESPONSE PROTOCOL:
        - If offer < 80% of disputed amount + penalty, it is a lowball.
        - Say: "This is a Lowball Trap. [Company] owes you ₹[original amount] + [20-50%] statutory penalty for mental agony. Their offer of ₹[X] is [Y]% of what they legally owe. Reject it."
        - Draft a counter-email they can copy-paste:
          SUBJECT: Re: Settlement Offer — Rejected. Revised Demand.
          BODY: I acknowledge your settlement offer of ₹[X]. This amount does not account for the statutory penalty for mental agony and litigation costs I am entitled to under Section 2(11) of the Consumer Protection Act, 2019. My revised demand is ₹[full amount]. You have 7 days to respond before I file with the District Consumer Commission via e-Daakhil.

        SCENARIO C — COMPANY THREATENS LEGAL ACTION / COUNTER-SUIT:
        Trigger phrases: "they are threatening", "said they'll sue", "legal team", "defamation", "counter notice"
        RESPONSE PROTOCOL:
        - Immediately calm the user: "This is a SLAPP tactic — Strategic Lawsuit Against Public Participation. It is a bluff designed to scare you into silence. In India, consumer complaints filed in good faith cannot be called defamatory."
        - Cite: "The Supreme Court in Rajnish Chadha v. HDFC Bank held that filing a consumer complaint is a legal right, not defamation."
        - Action: "Reply to their threat with this one line: 'My complaint is based on documented facts. I will proceed with the District Consumer Commission. Any legal action on your part will be treated as intimidation of a consumer complainant and reported to the NCDRC.'"

        SCENARIO D — COMPANY SAYS "CASE CLOSED" / IGNORED THE NOTICE:
        Trigger phrases: "no reply", "ignored", "said case closed", "ticket closed", "no response", "30 days passed"
        RESPONSE PROTOCOL:
        - Say: "Silence after a legal notice is your strongest weapon. 30 days of non-response is proof of willful negligence."
        - Present the escalation ladder:
          Step 1: "File with the National Consumer Helpline (NCH) — Call 1915. Free. Takes 10 minutes."
          Step 2: "File on the company's SEBI/RBI/IRDAI/TRAI portal (sector-specific). I will tell you the exact portal."
          Step 3: "File on e-Daakhil (edaakhil.nic.in) — The District Consumer Commission. ₹0 to ₹100 filing fee. No lawyer needed."
        - Then offer: "Shall I generate the e-Daakhil court filing package for you?"

        SCENARIO E — PARTIAL RESOLUTION / COMPANY ASKS FOR MORE TIME:
        Trigger phrases: "said give us more time", "7 more days", "processing", "under review", "escalated internally"
        RESPONSE PROTOCOL:
        - Say: "This is the Delay Loop. They are buying time hoping you give up."
        - Draft a deadline email: "Your complaint has been under review for [X] days. I am granting a final 48-hour extension. If the refund is not credited by [date], I will file with the District Consumer Commission the same day. No further extensions will be granted."

        GENERAL POST-STRIKE RULE: If the user says ANYTHING about what the company said after receiving the notice, always first ask "What exactly did they say or offer?" before giving advice, so you have the full picture.

        TONE RULE FOR ALL POST-STRIKE RESPONSES: Speak like a senior advocate who is genuinely angry on the user's behalf. Say "they are lying to you" not "this may constitute a violation." Say "this is illegal" not "this appears to be non-compliant." Be on the user's side, loudly and specifically.
        """

        # --- VISION AI DYNAMIC ROUTER ---
        chat_messages = []
        active_model = "llama-3.3-70b-versatile"

        if payload.image_base64:
            active_model = "llama-3.2-11b-vision-preview"
            chat_messages = [{
                "role": "user",
                "content": [
                    {"type": "text", "text": intake_prompt},
                    {"type": "image_url", "image_url": {"url": payload.image_base64}}
                ]
            }]
        else:
            chat_messages = [{"role": "user", "content": intake_prompt}]

        response = await client.chat.completions.create(
            model=active_model,
            messages=chat_messages,
            temperature=0.2,
            max_tokens=1200
        )
        ai_response = response.choices[0].message.content.strip()

        # --- 3. WAR ROOM TRIGGER (DYNAMIC ROUTER) ---
        # Strip punctuation and split into exact words to fix the "yesterday" bug
        user_msg_clean = payload.user_message.lower().replace(".", "").replace(",", "")
        words = user_msg_clean.split()
        
        exact_word_triggers = ["draft", "attack", "generate", "ready", "yes"]
        phrase_triggers = ["send it", "legal notice", "do it", "war room"]
        
        trigger_activated = any(trigger in words for trigger in exact_word_triggers) or any(phrase in user_msg_clean for phrase in phrase_triggers)
        
        if trigger_activated:
            
            # --- THE PRODUCTION AUTH GATE ---
            if not user:
                ai_response = "🛡️ **AUTHENTICATION REQUIRED**: I am ready to deploy the legal strike, but for security and record-keeping, you must sign in first. Please log in or create an account to secure your case history."
                return {"reply": ai_response, "require_auth": True}

            combined_context = f"{chat_history_text}\nUSER: {payload.user_message}"
            
            extraction_res = await client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{
                    "role": "system", 
                    "content": f"You are a data extractor. The user is currently in the '{user_sector}' sector. Identify the PRIMARY target company the user is complaining about. CRITICAL: Because this is the {user_sector} sector, prioritize the payment app, bank, or platform (e.g., Google Pay, PhonePe) and strictly IGNORE third-party merchants (e.g., Kuku FM, Swiggy) unless the user explicitly wants to sue the merchant. Reply with ONLY the exact primary company name. If none, reply 'NONE'."
                },
                {"role": "user", "content": combined_context}],
                temperature=0.0
            )
            
            detected_company = extraction_res.choices[0].message.content.strip().replace(".", "")
            
            # Ask user to confirm the detected company before drafting
            confirmed = payload.user_message.lower()
            company_confirmed = any(word in confirmed for word in ["yes", "correct", "right", "confirm", "that's right", "yep", "yeah"])

            if "NONE" not in detected_company.upper() and len(detected_company) > 1 and company_confirmed:
                from war_room import run_legal_war_room
                
                # ── NEW: VECTOR RAG VAULT SEARCH ──
                hf_api_url = "https://router.huggingface.co/hf-inference/models/sentence-transformers/all-MiniLM-L6-v2/pipeline/feature-extraction"
                hf_headers = {"Authorization": f"Bearer {os.getenv('HF_TOKEN')}"}
                
                # 🛡️ MATH PATCH: Use microscopic non-zero values to prevent PostgreSQL Division-by-Zero NaN crashes
                query_vector = [0.0001] * 384
                try:
                    async with httpx.AsyncClient(timeout=10.0) as http_client:
                        hf_response = await http_client.post(hf_api_url, headers=hf_headers, json={"inputs": combined_context})
                        if hf_response.status_code == 200:
                            res_json = hf_response.json()
                            # 🛡️ ANTI-CRASH PATCH: Safely handle HF cold-start dictionary errors
                            if isinstance(res_json, list) and len(res_json) > 0:
                                query_vector = res_json[0] if isinstance(res_json[0], list) else res_json
                            elif isinstance(res_json, dict) and "error" in res_json:
                                logger.warning(f"HF Model Cold Start in chat: {res_json.get('error')}")
                except Exception as e:
                    logger.error(f"HF Embedding failed: {e}")

                # --- NEW: 100% ACCURATE RAG PIPELINE ---
                db_sector_tag = ai_master_category

                # ANTI-HALLUCINATION FALLBACK: Never default to generic CPA. Use Hardcoded Sector Rules if DB fails.
                retrieved_laws = f"MANDATORY SECTOR LAWS:\n{sector_knowledge}\nGENERAL STATUTES: Apply Section 2(11) [Deficiency in Service] and Section 2(47) [Unfair Trade Practice] of the Consumer Protection Act, 2019."
                
                if supabase:
                    try:
                        # 🛡️ ASYNC PATCH: Offload heavy DB Vector Search to background thread
                        def execute_vault_search():
                            vault_client = supabase_admin or supabase
                            res = vault_client.rpc('match_legal_clauses', {
                                'query_embedding': query_vector,
                                'match_threshold': 0.2, 
                                'match_count': 4,
                                'filter': {'sector': db_sector_tag}
                            }).execute()
                            
                            if not res.data or len(res.data) == 0:
                                logger.info(f"0 results for '{db_sector_tag}'. Searching entire Vault...")
                                res = vault_client.rpc('match_legal_clauses', {
                                    'query_embedding': query_vector,
                                    'match_threshold': 0.2, 
                                    'match_count': 4
                                }).execute()
                            return res

                        vault_res = await asyncio.to_thread(execute_vault_search)

                        # Inject the real laws from your PDFs
                        if vault_res and hasattr(vault_res, 'data') and vault_res.data and len(vault_res.data) > 0:
                            retrieved_laws = ""
                            for match in vault_res.data:
                                raw_source = match.get('source_document', 'Legal Vault')
                                # Strip filename artifacts so agents cite proper law names, not filenames
                                clean_source = raw_source.replace(".pdf", "").replace("_", " ").replace("-", " ").strip()
                                retrieved_laws += f"[Source: {clean_source}]\n{match['content']}\n\n"
                            logger.info("SUCCESS: Loaded exact PDF laws from Supabase.")
                    except Exception as e:
                        logger.error(f"Vault Search completely failed: {e}")

                strike_prompt = f"""
                Draft a ruthless legal notice against {detected_company} based on this conversation:
                {combined_context}
                
                MANDATORY LEGAL FRAMEWORK (DO NOT HALLUCINATE):
                You MUST explicitly cite the following laws which were extracted directly from the official Indian Legal Vault. Do not invent section numbers. Use these exact clauses:
                
                {retrieved_laws}
                
                SPECIFIC DEMAND: Demand immediate resolution, a full refund, and maximum statutory penalties allowed by the cited laws.
                """

                logger.info(f"RAW LAWS PULLED FROM SUPABASE FOR {db_sector_tag}: {len(retrieved_laws)} chars loaded.")

                # TRIGGER THE 5-WAY WEB WAR ROOM (Threaded so it doesn't block the server)
                logger.info(f"War Room requested for {detected_company}. Waiting for available clearance...")

                try:
                    async with war_room_semaphore:
                        logger.info(f"War Room clearance granted for {detected_company}. Processing...")
                        war_room_draft = await asyncio.wait_for(
                            asyncio.to_thread(
                                run_legal_war_room,
                                user_message=strike_prompt,
                                retrieved_laws=retrieved_laws
                            ),
                            timeout=85.0
                        )
                except asyncio.TimeoutError:
                    logger.error(f"War Room hit 85s timeout for {detected_company}.")
                    return {"reply": "⚠️ The Strategist encountered heavy network traffic and timed out. Please type 'yes' to deploy the strike again.", "session_id": session_id}
                except Exception as e:
                    logger.error(f"War Room execution failed: {e}")
                    war_room_draft = None
                if not war_room_draft or len(war_room_draft.strip()) < 100:
                    war_room_draft = "⚠️ The War Room encountered an issue generating your full battle package. Please type 'yes' again to retry."

                
                # --- NEW: 1-CLICK DISPATCH DATA EXTRACTOR ---
                target_email = "grievance@company.com"
                for db_company, db_data in VERIFIED_DB.items():
                    # 🛡️ CORPORATE MATCHING PATCH: Bidirectional fuzzy match prevents email misfires
                    c_det = detected_company.lower()
                    c_db = db_company.lower()
                    if c_det in c_db or c_db in c_det:
                        target_email = db_data.get("email", target_email)
                        break
                        
                mail_subject = f"URGENT PRE-LITIGATION NOTICE: {detected_company.upper()}"

                # Strip Section 2 from email body — Battle Intelligence is for user only
                if "SECTION 2" in war_room_draft:
                    email_body = war_room_draft.split("SECTION 2")[0].strip()
                elif "⚔️" in war_room_draft:
                    email_body = war_room_draft.split("⚔️")[0].strip()
                else:
                    email_body = war_room_draft.strip()
                
                # 🛡️ FORMATTING PATCH: Strip AI formatting headers so the email looks human-written
                email_body = email_body.replace("SECTION 1 — LEGAL NOTICE:", "").replace("SECTION 1 - LEGAL NOTICE:", "").replace("SECTION 1:", "").strip()

                # We return the visual response AND the raw data for the buttons
                ai_response = f"⚔️ **WAR ROOM STRIKE GENERATED FOR {detected_company.upper()}**\n\n{war_room_draft}"
                
                # Save to DB
                if user and session_id and supabase:
                    supabase.table('messages').insert({"session_id": session_id, "role": "ai", "content": ai_response}).execute()

                return {
                    "reply": ai_response, 
                    "session_id": session_id,
                    "dispatch_data": {
                        "email": target_email,
                        "subject": mail_subject,
                        "body": email_body,
                        "company_name": detected_company,
                        "amount": "the disputed amount" # Fallback since exact amount isn't extracted here
                    }
                }
            
            elif "NONE" in detected_company.upper() or len(detected_company) <= 1:
                ai_response = "I'm ready to strike, but I need you to confirm the company name one last time. Is it PhonePe, Amazon, or someone else?"
            else:
                ai_response = f"I've identified **{detected_company}** as the target. Can you confirm this is correct? Reply **'yes'** and I'll deploy the full legal strike."
                if user and session_id and supabase:
                    supabase.table('messages').insert({"session_id": session_id, "role": "ai", "content": ai_response}).execute()
                return {"reply": ai_response, "session_id": session_id}

        # --- 4. LOG NORMAL CHAT RESPONSE ---
        if user and session_id and supabase:
            supabase.table('messages').insert({"session_id": session_id, "role": "ai", "content": ai_response}).execute()

        return {"reply": ai_response, "session_id": session_id}

        
        
    except Exception as e:
        logger.error(f"Chat Error:\n{traceback.format_exc()}")
        return {"reply": "⚠️ The Strategist is recalibrating. Please try again."}
    
# --- SIDEBAR HISTORY ENDPOINTS ---
@app.get("/api/sessions")
async def get_chat_sessions(user = Depends(get_current_user)):
    try:
        res = supabase.table('chat_sessions').select('*').eq('user_id', user.id).order('created_at', desc=True).execute()
        return {"sessions": res.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to retrieve sessions")

@app.get("/api/messages/{session_id}")
async def get_session_messages(session_id: str, user = Depends(get_current_user)):
    try:
        session_res = supabase.table('chat_sessions').select('user_id').eq('id', session_id).execute()
        if not session_res.data or session_res.data[0]['user_id'] != user.id:
            raise HTTPException(status_code=403, detail="Unauthorized")
        res = supabase.table('messages').select('*').eq('session_id', session_id).order('created_at', desc=False).execute()
        return {"messages": res.data}
    except HTTPException: raise
    except Exception as e: raise HTTPException(status_code=500, detail="Failed to retrieve messages")

@app.delete("/api/sessions/{session_id}")
async def delete_chat_session(session_id: str, user = Depends(get_current_user)):
    """Deletes a specific case and all its messages (DPDP Act Compliance)."""
    try:
        # 1. Verify ownership (Security Check)
        session_res = supabase.table('chat_sessions').select('user_id').eq('id', session_id).execute()
        if not session_res.data or session_res.data[0]['user_id'] != user.id:
            raise HTTPException(status_code=403, detail="Unauthorized to delete this case.")
        
        # 2. Delete all messages tied to this case
        supabase.table('messages').delete().eq('session_id', session_id).execute()
        
        # 3. Delete the case session itself
        supabase.table('chat_sessions').delete().eq('id', session_id).execute()
        
        return {"status": "success", "message": "Case permanently deleted."}
    except HTTPException: 
        raise
    except Exception as e: 
        logger.error(f"Failed to delete session: {e}")
        raise HTTPException(status_code=500, detail="Database deletion failed.")

@app.post("/api/edakhil-package")
@limiter.limit("5/minute") 
async def generate_edakhil(request: Request, payload: EdakhilRequest, user = Depends(get_current_user)):
    if not supabase: raise HTTPException(status_code=500, detail="Database offline")
    
    # 🔒 SECURITY PATCH: Verify case ownership
    session_res = supabase.table('chat_sessions').select('user_id').eq('id', payload.session_id).execute()
    if not session_res.data or session_res.data[0]['user_id'] != user.id:
        raise HTTPException(status_code=403, detail="Unauthorized access to case history.")
        
    # 🛡️ LEGAL COMPLIANCE PATCH: e-Daakhil requires physical registered addresses, not emails.
    company_address = VERIFIED_DB.get(payload.company_name, {}).get("address", "[INSERT PHYSICAL REGISTERED OFFICE ADDRESS HERE]")
    
    # 1. Pull the chat history so the AI knows the exact facts of the case
    past_messages = supabase.table('messages').select('role, content').eq('session_id', payload.session_id).order('created_at', desc=False).execute()
    
    # 🛡️ DOSSIER TOKEN PATCH: Keep the AI focused on the last 8 interactions so the output doesn't get cut off
    recent_messages = past_messages.data[-8:] if past_messages.data else []
    history_text = "\n".join([f"{m['role']}: {m['content']}" for m in recent_messages]) if recent_messages else "No history found."

    # 2. The Supreme Court System Prompt for HTML Generation
    court_prompt = f"""
    You are drafting a formal consumer complaint for the District Consumer Disputes Redressal Commission in India.
    
    COMPLAINANT: {payload.user_name}, residing at {payload.user_address}
    OPPOSITE PARTY: {payload.company_name}, {company_address}
    
    CASE HISTORY:
    {history_text}
    
    CRITICAL RULE: You must output the response in raw HTML format using <b>, <u>, <i>, <p>, and <br> tags. DO NOT use markdown like ** or ##. 
    
    Format exactly like this:
    <div style="text-align: center;"><b>BEFORE THE DISTRICT CONSUMER DISPUTES REDRESSAL COMMISSION</b></div>
    <br>
    <b>IN THE MATTER OF:</b><br>
    {payload.user_name} ... COMPLAINANT<br>
    <b>VERSUS</b><br>
    {payload.company_name} ... OPPOSITE PARTY<br>
    <hr>
    
    <b><u>INDEX OF ANNEXURES</u></b><br>
    <ul>
        <li><b>Annexure A:</b> Copy of the original Invoice/Receipt.</li>
        <li><b>Annexure B:</b> Photographic evidence of the defect/deficiency.</li>
        <li><b>Annexure C:</b> Copy of all email/chat communications with the Opposite Party proving their refusal to resolve the issue.</li>
    </ul>
    <br>

    <b><u>1. MEMO OF PARTIES</u></b><br>
    <p>[Draft the details]</p>
    <b><u>2. LIST OF DATES AND EVENTS</u></b><br>
    <p>[Draft chronological timeline]</p>
    <b><u>3. COMPLAINT UNDER SECTION 35 OF THE CONSUMER PROTECTION ACT, 2019</u></b><br>
    <p><b>A. Jurisdiction:</b> [Draft]</p>
    <p><b>B. Facts of the Case:</b> [Draft from history]</p>
    <p><b>C. Deficiency in Service & Unfair Trade Practice:</b> [Draft]</p>
    <p><b>D. Cause of Action:</b> [Draft]</p>
    <b><u>4. PRAYER FOR RELIEF</u></b><br>
    <p>[Draft the demands including refund, compensation for mental agony, and litigation costs]</p>
    <br><br><br>
    <b>COMPLAINANT (PARTY-IN-PERSON)</b><br>
    Signature: ___________________
    """

    try:
        response = await client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": court_prompt}],
            temperature=0.2, max_tokens=2500
        )
        dossier = response.choices[0].message.content.strip()
        # 🛡️ BULLETPROOF HTML EXTRACTION: Handle conversational filler placed before the markdown fences
        if "```html" in dossier:
            dossier = dossier.split("```html")[1].split("```")[0].strip()
        elif "```" in dossier:
            dossier = dossier.split("```")[1].split("```")[0].strip()
        
        return {"status": "success", "court_dossier": dossier}
    except Exception as e:
        logger.error(f"Court Generation Failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate court documents.")

@app.get("/api/matrix/{company_name}")
async def escalation_matrix(company_name: str):
    if company_name not in VERIFIED_DB:
        return {"company": company_name, "step_1_email": "Find general support email online", "step_2_social_pressure": f"Search Twitter/X for @{company_name.replace(' ', '')} and post your generated notice.", "step_3_portal": "File on the National Consumer Helpline (NCH) app."}
    data = VERIFIED_DB[company_name]
    return {"company": company_name, "step_1_email": data["email"], "step_2_social_pressure": f"Tweet at {data.get('twitter', 'their handle')} using #KarmaClaims", "step_3_portal": data.get('portal', 'No portal found')}