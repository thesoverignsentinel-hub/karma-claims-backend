import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator
from dotenv import load_dotenv
from groq import AsyncGroq
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ⚡ KARMA CLAIMS — LEGAL STRIKE ENGINE
# Backend v2.6 | Production-Ready
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S"
)
logger = logging.getLogger("karma-claims")

load_dotenv()
API_KEY = os.getenv("GROQ_API_KEY")
if not API_KEY:
    raise RuntimeError("[FATAL] GROQ_API_KEY is not set. System cannot start.")

# ── Allowed Origins (replace * in prod) ──────────────────────────────────────
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SECTION 1 — VERIFIED CORPORATE DATABASE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

VERIFIED_DB: dict[str, dict] = {
    # ── BANKING & CARDS (Regulator: RBI) ──
    "HDFC Bank (HDFC Bank Limited)": {"email": "pno@hdfcbank.com", "industry": "Banking", "regulator": "RBI"},
    "SBI (State Bank of India)": {"email": "crcf.sbi@sbi.co.in", "industry": "Banking", "regulator": "RBI"},
    "ICICI Bank (ICICI Bank Ltd)": {"email": "headservicequality@icicibank.com", "industry": "Banking", "regulator": "RBI"},
    "Axis Bank (Axis Bank Ltd)": {"email": "pno@axisbank.com", "industry": "Banking", "regulator": "RBI"},
    "Kotak Mahindra Bank": {"email": "nodalofficer@kotak.com", "industry": "Banking", "regulator": "RBI"},
    "Punjab National Bank (PNB)": {"email": "care@pnb.co.in", "industry": "Banking", "regulator": "RBI"},
    "Bank of Baroda (BOB)": {"email": "cs.ho@bankofbaroda.com", "industry": "Banking", "regulator": "RBI"},
    "SBI Card (SBI Cards & Payment Services)": {"email": "nodalofficer@sbicard.com", "industry": "Fintech", "regulator": "RBI"},

    # ── FINTECH & BROKERS (Regulator: RBI / SEBI) ──
    "Google Pay (Google India Digital Services)": {"email": "nodal-gpay@google.com", "industry": "Fintech", "regulator": "RBI"},
    "PhonePe (PhonePe Private Limited)": {"email": "nodal@phonepe.com", "industry": "Fintech", "regulator": "RBI"},
    "Paytm (One97 Communications Ltd)": {"email": "nodalofficer@paytm.com", "industry": "Fintech", "regulator": "RBI"},
    "CRED (Dreamplug Technologies Pvt Ltd)": {"email": "grievanceofficer@cred.club", "industry": "Fintech", "regulator": "RBI"},
    "Zerodha (Zerodha Broking Ltd)": {"email": "complaints@zerodha.com", "industry": "Fintech", "regulator": "SEBI"},
    "Groww (Nextbillion Technology Pvt Ltd)": {"email": "grievances@groww.in", "industry": "Fintech", "regulator": "SEBI"},
    "Upstox (RKSV Securities India Pvt Ltd)": {"email": "complaints@upstox.com", "industry": "Fintech", "regulator": "SEBI"},

    # ── E-COMMERCE & RETAIL (Regulator: CCPA) ──
    "Amazon India (Amazon Seller Services)": {"email": "grievance-officer@amazon.in", "industry": "E-Commerce", "regulator": "CCPA"},
    "Flipkart (Flipkart Internet Pvt Ltd)": {"email": "grievance.officer@flipkart.com", "industry": "E-Commerce", "regulator": "CCPA"},
    "Myntra (Myntra Designs Pvt Ltd)": {"email": "grievanceofficer@myntra.com", "industry": "E-Commerce", "regulator": "CCPA"},
    "Meesho (Fashnear Technologies Pvt Ltd)": {"email": "grievance@meesho.com", "industry": "E-Commerce", "regulator": "CCPA"},
    "Nykaa (FSN E-Commerce Ventures Ltd)": {"email": "grievanceofficer@nykaa.com", "industry": "E-Commerce", "regulator": "CCPA"},
    "Ajio (Reliance Retail Ltd)": {"email": "grievance.officer@ajio.com", "industry": "E-Commerce", "regulator": "CCPA"},
    "Tata Cliq (Tata UniStore Limited)": {"email": "grievance.officer@tatacliq.com", "industry": "E-Commerce", "regulator": "CCPA"},

    # ── FOOD & QUICK COMMERCE (Regulator: CCPA) ──
    "Zomato (Zomato Limited)": {"email": "grievance@zomato.com", "industry": "E-Commerce", "regulator": "CCPA"},
    "Swiggy (Bundl Technologies Pvt Ltd)": {"email": "grievances@swiggy.in", "industry": "E-Commerce", "regulator": "CCPA"},
    "Blinkit (Grofers India Pvt Ltd)": {"email": "grievance@blinkit.com", "industry": "E-Commerce", "regulator": "CCPA"},
    "Zepto (Kiranakart Technologies Pvt Ltd)": {"email": "grievance@zeptonow.com", "industry": "E-Commerce", "regulator": "CCPA"},
    "BigBasket (Innovative Retail Concepts)": {"email": "grievanceofficer@bigbasket.com", "industry": "E-Commerce", "regulator": "CCPA"},

    # ── RIDE SHARING & MOBILITY (Regulator: CCPA / MoRTH) ──
    "Ola Cabs (ANI Technologies Pvt Ltd)": {"email": "grievance@olacabs.com", "industry": "E-Commerce", "regulator": "CCPA"},
    "Uber India (Uber India Systems Pvt Ltd)": {"email": "grievanceofficer_india@uber.com", "industry": "E-Commerce", "regulator": "CCPA"},
    "Rapido (Roppen Transportation Services)": {"email": "grievance@rapido.bike", "industry": "E-Commerce", "regulator": "CCPA"},
    "RedBus (Ibibo Group Pvt Ltd)": {"email": "grievanceofficer@redbus.in", "industry": "E-Commerce", "regulator": "CCPA"},

    # ── TRAVEL & AIRLINES (Regulator: DGCA / CCPA) ──
    "MakeMyTrip (MakeMyTrip India Pvt Ltd)": {"email": "nodalofficer@makemytrip.com", "industry": "E-Commerce", "regulator": "CCPA"},
    "Goibibo (Ibibo Group Pvt Ltd)": {"email": "grievanceofficer@goibibo.com", "industry": "E-Commerce", "regulator": "CCPA"},
    "Cleartrip (Cleartrip Pvt Ltd)": {"email": "grievanceofficer@cleartrip.com", "industry": "E-Commerce", "regulator": "CCPA"},
    "Indigo Airlines (InterGlobe Aviation)": {"email": "nodalofficer@goindigo.in", "industry": "Airlines", "regulator": "DGCA"},
    "Air India (Air India Limited)": {"email": "nodalofficer@airindia.com", "industry": "Airlines", "regulator": "DGCA"},
    "SpiceJet (SpiceJet Limited)": {"email": "nodalofficer@spicejet.com", "industry": "Airlines", "regulator": "DGCA"},
    "Akasa Air (SNV Aviation Pvt Ltd)": {"email": "nodalofficer@akasaair.com", "industry": "Airlines", "regulator": "DGCA"},

    # ── TELECOM & DTH (Regulator: TRAI) ──
    "Reliance Jio (Reliance Jio Infocomm)": {"email": "appellate@jio.com", "industry": "Telecom", "regulator": "TRAI"},
    "Airtel (Bharti Airtel Limited)": {"email": "nodalofficer@airtel.com", "industry": "Telecom", "regulator": "TRAI"},
    "Vi / Vodafone Idea (Vodafone Idea Ltd)": {"email": "appellate.officer@vodafoneidea.com", "industry": "Telecom", "regulator": "TRAI"},
    "BSNL (Bharat Sanchar Nigam Limited)": {"email": "pgportal@bsnl.co.in", "industry": "Telecom", "regulator": "TRAI"},
    "Tata Play (Tata Play Limited)": {"email": "nodalofficer@tataplay.com", "industry": "Telecom", "regulator": "TRAI"},

    # ── INSURANCE (Regulator: IRDAI) ──
    "LIC India (Life Insurance Corporation)": {"email": "co_complaints@licindia.com", "industry": "Insurance", "regulator": "IRDAI"},
    "Star Health (Star Health & Allied Insurance)": {"email": "grievance@starhealth.in", "industry": "Insurance", "regulator": "IRDAI"},
    "HDFC Life (HDFC Life Insurance Co)": {"email": "grievance@hdfclife.com", "industry": "Insurance", "regulator": "IRDAI"},
    "SBI Life (SBI Life Insurance Co)": {"email": "info@sbilife.co.in", "industry": "Insurance", "regulator": "IRDAI"},
    "Policybazaar (PB Fintech Ltd)": {"email": "grievance@policybazaar.com", "industry": "Insurance", "regulator": "IRDAI"},
    "Acko (Acko General Insurance Ltd)": {"email": "grievance@acko.com", "industry": "Insurance", "regulator": "IRDAI"},

    # ── EDTECH (Regulator: CCPA) ──
    "Byjus (Think and Learn Pvt Ltd)": {"email": "grievances@byjus.com", "industry": "EdTech", "regulator": "CCPA"},
    "Unacademy (Sorting Hat Technologies)": {"email": "grievance@unacademy.com", "industry": "EdTech", "regulator": "CCPA"},
    "Physics Wallah (PhysicsWallah Pvt Ltd)": {"email": "support@pw.live", "industry": "EdTech", "regulator": "CCPA"},
    "UpGrad (UpGrad Education Pvt Ltd)": {"email": "grievance@upgrad.com", "industry": "EdTech", "regulator": "CCPA"}
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SECTION 2 — RATE LIMITER & APP SETUP
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

limiter = Limiter(key_func=get_remote_address)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("⚡ Karma Claims Strike Engine is online.")
    yield
    logger.info("System shutdown complete.")

app = FastAPI(
    title="Karma Claims — Legal Strike API",
    version="2.6.0",
    docs_url="/docs",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,  
    allow_credentials=False,         
    allow_methods=["*"],
    allow_headers=["*"],
)

client = AsyncGroq(api_key=API_KEY)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SECTION 3 — REQUEST SCHEMA & VALIDATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_INJECTION_PATTERNS = [
    "ignore above", "ignore previous", "disregard", "system:",
    "###", "---", "```", "<|", "|>", "prompt:", "assistant:",
    "override", "jailbreak", "forget instructions",
]

class DisputeRequest(BaseModel):
    user_name: str
    user_email: str
    user_phone: str
    company_name: str
    order_id: str
    disputed_amount: str
    complaint_details: str

    @field_validator("user_name", "company_name", "order_id", "complaint_details", "user_email", "user_phone", mode="before")
    @classmethod
    def must_not_be_empty(cls, v: str, info) -> str:
        if not v or not v.strip():
            raise ValueError(f"{info.field_name} must not be empty.")
        return v.strip()
        
    @field_validator("complaint_details", mode="before")
    @classmethod
    def sanitize_and_truncate(cls, v: str) -> str:
        """Zero-tolerance prompt injection block that preserves original formatting."""
        v_lower = v.lower()
        for pattern in _INJECTION_PATTERNS:
            if pattern in v_lower:
                raise ValueError("Security Alert: Invalid characters or prompt injection detected.")
        return v[:1000].strip()

    @field_validator("company_name")
    @classmethod
    def validate_company(cls, v: str) -> str:
        if v not in VERIFIED_DB:
            raise ValueError(f"'{v}' is not in the verified company database.")
        return v

    @field_validator("disputed_amount")
    @classmethod
    def validate_amount(cls, v: str) -> str:
        try:
            amount = float(v)
            if amount <= 0:
                raise ValueError("Disputed amount must be greater than zero.")
        except (TypeError, ValueError):
            raise ValueError("Disputed amount must be a valid positive number.")
        return v

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SECTION 4 — AI SYSTEM PROMPT BUILDER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def build_system_prompt(industry: str, regulator: str) -> str:
    """Build a dynamically targeted system prompt based on industry and regulator."""
    
    regulatory_context = {
        "Fintech": (
            "Cite the 'RBI Circular on Limiting Liability of Customers in Unauthorised Electronic Banking Transactions (DBR.No.Leg.BC.78/09.07.005/2017-18)'. "
            "Demand shadow credit within 10 working days or threaten escalation to the RBI Integrated Ombudsman Scheme at cms.rbi.org.in."
        ),
        "Banking": (
            "Cite the 'RBI Banking Ombudsman Scheme 2006 (as amended in 2017)' and the Banking Regulation Act. "
            "Demand resolution within 30 days per RBI mandate or threaten direct escalation to the RBI Ombudsman and the CIBIL reporting of bank negligence."
        ),
        "E-Commerce": (
            "Cite 'Rule 4(4) and Rule 7 of the Consumer Protection (E-Commerce) Rules, 2020'. "
            "Threaten a Chargeback Dispute for 'Service Not Rendered' with their payment gateway partner. "
            "Also invoke Section 9 of the Consumer Protection Act, 2019 for deficiency of service."
        ),
        "Telecom": (
            "Cite 'TRAI Telecom Consumers Complaint Redressal Regulations, 2012' and the Telecom Commercial Communications Customer Preference Regulations. "
            "Threaten escalation to the Telecom Ombudsman (TRAI CGPDTM portal) and demand resolution per the 30-day TRAI mandate."
        ),
        "Airlines": (
            "Cite 'DGCA Civil Aviation Requirements (CAR) Section 3, Series M, Part I' on Passenger Service. "
            "Invoke EU261/2004 equivalent protections for Indian domestic passengers. "
            "Threaten DGCA formal complaint and Ministry of Civil Aviation intervention."
        ),
        "Insurance": (
            "Cite 'IRDAI Regulations on Protection of Policyholders' Interests, 2017' and the Insurance Act, 1938. "
            "Demand settlement within 30 days per IRDAI mandate or threaten escalation to the IRDAI Bima Bharosa portal."
        ),
        "EdTech": (
            "Cite 'UGC Guidelines on Online Courses' and Consumer Protection Act, 2019, Section 2(9) on product liability. "
            "Threaten escalation to the CCPA and NCPCR for predatory marketing targeting students."
        ),
        "Real Estate": (
            "Cite 'Section 31 of the Real Estate (Regulation and Development) Act, 2016 (RERA)'. "
            "Threaten filing a complaint with the state RERA authority and demanding penalty under Section 63 of RERA."
        ),
    }

    industry_rule = regulatory_context.get(
        industry,
        "Cite the Consumer Protection Act, 2019, and relevant sector-specific regulations."
    )

    return (
        "You are a coldly strategic, fiercely effective Indian consumer rights advocate. "
        "Your singular mission: extract an immediate refund or settlement for the consumer. "
        "Draft a formal, legally intimidating grievance email that makes refunding immediately "
        "appear far cheaper than the regulatory and reputational fallout of non-compliance.\n\n"
        f"INDUSTRY: {industry} | PRIMARY REGULATOR: {regulator}\n\n"
        f"REGULATORY ARSENAL:\n{industry_rule}\n\n"
        "ADDITIONAL UNIVERSAL THREATS (use where applicable):\n"
        "- If hidden charges exist: Cite 'CCPA Guidelines for Prevention and Regulation of Dark Patterns, 2023'.\n"
        "- Frame the issue as a 'systemic deceptive practice' warranting CCPA investigation under Section 18 of CPA 2019.\n"
        "- Mention potential Consumer Court filing under Section 34 of CPA 2019 if not resolved within 48 hours.\n\n"
        "TONE: Coldly professional. Legally precise. Financially calculating. Zero emotion. Maximum pressure.\n"
        "FORMAT: Begin with '[URGENT LEGAL NOTICE — 48-HOUR RESOLUTION REQUIRED]'. "
        "Use numbered sections. "
        "Keep to ~400 words. Do not add pleasantries."
    )

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SECTION 5 — THE STRIKE ENDPOINT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@app.post("/generate-draft")
@limiter.limit("5/minute")
async def generate_legal_draft(request: Request, payload: DisputeRequest):
    """
    Generate a legally-targeted grievance email draft.
    Rate limited to 5 requests/minute per IP.
    """
    target_data = VERIFIED_DB[payload.company_name]
    target_email = target_data["email"]
    industry = target_data["industry"]
    regulator = target_data["regulator"]

    system_prompt = build_system_prompt(industry, regulator)

    user_message = (
        f"TARGET ENTITY: {payload.company_name}\n"
        f"INDUSTRY: {industry} | REGULATOR: {regulator}\n"
        f"ORDER/TRANSACTION ID: {payload.order_id}\n"
        f"DISPUTED AMOUNT: ₹{payload.disputed_amount}\n"
        f"CONSUMER NAME: {payload.user_name}\n"
        f"CONSUMER PHONE: {payload.user_phone}\n"
        f"CONSUMER EMAIL: {payload.user_email}\n\n"
        f"INCIDENT DESCRIPTION:\n{payload.complaint_details}"
    )

    try:
        response = await client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt + "\nDO NOT add a signature block at the end. The system will append it."},
                {"role": "user", "content": user_message},
            ],
            temperature=0.25,      
            max_tokens=1024,
            top_p=0.9,
        )

        # Grab the raw AI output
        raw_draft = response.choices[0].message.content.strip()
        
        # Hardcode the proofs and signature perfectly every time
        signature_block = (
            "\n\nPlease find attached the relevant transaction proofs, screenshots, and evidence supporting this claim.\n\n"
            "Sincerely,\n"
            f"{payload.user_name}\n"
            f"Phone: {payload.user_phone}\n"
            f"Email: {payload.user_email}"
        )
        
        # Combine them
        draft_body = raw_draft + signature_block

        company_short = payload.company_name.split("(")[0].strip()
        subject_line = (
            f"URGENT LEGAL NOTICE | {company_short} | "
            f"Ref: {payload.order_id} | ₹{payload.disputed_amount}"
        )

        logger.info(
            "Strike generated | company=%s | amount=%s | tokens_used=%s",
            company_short,
            payload.disputed_amount,
            response.usage.total_tokens if response.usage else "N/A",
        )

        return {
            "target_email": target_email,
            "subject": subject_line,
            "body": draft_body,
            "regulator": regulator,
            "industry": industry,
        }

    except Exception as e:
        logger.error("Groq API failure | error=%s", str(e))
        raise HTTPException(
            status_code=502,
            detail="Strike engine unavailable. Please retry in a moment."
        )

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SECTION 6 — HEALTH CHECK
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@app.get("/health")
async def health_check():
    return {
        "status": "online",
        "system": "Karma Claims Strike Engine",
        "version": "2.6.0",
        "companies_loaded": len(VERIFIED_DB),
    }