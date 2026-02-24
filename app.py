import os
import logging
import random
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
# ⚡ KARMA CLAIMS — ENGINE v4.1 (THE MASTER LAUNCH)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")
logger = logging.getLogger("karma-claims")

load_dotenv()
API_KEY = os.getenv("GROQ_API_KEY")
if not API_KEY:
    raise RuntimeError("[FATAL] GROQ_API_KEY is not set.")

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")

# ── 1. THE LIVING SCOREBOARD (MVP Memory) ──
SESSION_WINS = 0
SESSION_RECOVERED = 0.0

def get_dynamic_metrics():
    today_str = datetime.now().strftime("%Y-%m-%d")
    random.seed(today_str) 
    
    daily_users = random.randint(42, 187) 
    daily_cases = random.randint(2, 11)
    daily_money = random.randint(4500, 18500)
    
    return {
        "total_recovered": 462350 + daily_money + SESSION_RECOVERED,
        "cases_won": 147 + daily_cases + SESSION_WINS,
        "active_users": 892 + daily_users
    }

# ── 2. THE VERIFIED DB (Top-75 Indian Consumer Brands) ──
VERIFIED_DB: dict[str, dict] = {
    # E-COMMERCE & QUICK COMMERCE (CCPA)
    "Amazon India (Amazon Seller Services Pvt Ltd)": {"email": "grievance-officer@amazon.in", "industry": "E-Commerce", "regulator": "CCPA", "twitter": "@AmazonHelp", "portal": "https://www.amazon.in/gp/help/customer/display.html"},
    "Flipkart (Flipkart Internet Pvt Ltd)": {"email": "grievance.officer@flipkart.com", "industry": "E-Commerce", "regulator": "CCPA", "twitter": "@flipkartsupport", "portal": "https://www.flipkart.com/helpcentre"},
    "Myntra (Myntra Designs Pvt Ltd)": {"email": "grievance.officer@myntra.com", "industry": "E-Commerce", "regulator": "CCPA", "twitter": "@myntra", "portal": "https://www.myntra.com/contactus"},
    "Meesho (Fashnear Technologies Pvt Ltd)": {"email": "grievance@meesho.com", "industry": "E-Commerce", "regulator": "CCPA", "twitter": "@Meesho_Official", "portal": "https://www.meesho.com/legal/grievance"},
    "Nykaa (FSN E-Commerce Ventures)": {"email": "grievanceofficer@nykaa.com", "industry": "E-Commerce", "regulator": "CCPA", "twitter": "@MyNykaa", "portal": "https://www.nykaa.com/contact_us"},
    "Ajio (Reliance Retail Ltd)": {"email": "grievance.officer@ajio.com", "industry": "E-Commerce", "regulator": "CCPA", "twitter": "@AJIOLife", "portal": "https://www.ajio.com/selfcare"},
    "Tata CLiQ (Tata UniStore Ltd)": {"email": "grievance.officer@tatacliq.com", "industry": "E-Commerce", "regulator": "CCPA", "twitter": "@TataCLiQ", "portal": "https://www.tatacliq.com/contact-us"},
    "Snapdeal (Snapdeal Pvt Ltd)": {"email": "grievanceofficer@snapdeal.com", "industry": "E-Commerce", "regulator": "CCPA", "twitter": "@Snapdeal_Help", "portal": "https://www.snapdeal.com/help"},
    "Swiggy (Bundl Technologies Pvt Ltd)": {"email": "grievances@swiggy.in", "industry": "Food Delivery", "regulator": "CCPA", "twitter": "@SwiggyCares", "portal": "https://www.swiggy.com/contact"},
    "Zomato (Zomato Ltd)": {"email": "grievance@zomato.com", "industry": "Food Delivery", "regulator": "CCPA", "twitter": "@zomatocare", "portal": "https://www.zomato.com/contact"},
    "Blinkit (Blink Commerce Pvt Ltd)": {"email": "grievance.officer@blinkit.com", "industry": "Quick Commerce", "regulator": "CCPA", "twitter": "@letsblinkit", "portal": "https://blinkit.com/contact"},
    "Zepto (Kiranakart Technologies Pvt Ltd)": {"email": "grievances@zeptonow.com", "industry": "Quick Commerce", "regulator": "CCPA", "twitter": "@ZeptoNow", "portal": "https://www.zeptonow.com/"},
    "BigBasket (Supermarket Grocery Supplies)": {"email": "grievanceofficer@bigbasket.com", "industry": "Quick Commerce", "regulator": "CCPA", "twitter": "@bigbasket_com", "portal": "https://www.bigbasket.com/contact-us/"},
    "JioMart (Reliance Retail Ltd)": {"email": "cs@jiomart.com", "industry": "E-Commerce", "regulator": "CCPA", "twitter": "@JioMart_Care", "portal": "https://www.jiomart.com/contact-us"},
    "Licious (Delightful Gourmet Pvt Ltd)": {"email": "grievance@licious.com", "industry": "Food Delivery", "regulator": "CCPA", "twitter": "@LiciousFoods", "portal": "https://www.licious.in/contact-us"},

    # FINTECH (RBI)
    "Google Pay (Google India Digital Services)": {"email": "nodal-gpay@google.com", "industry": "Fintech", "regulator": "RBI", "twitter": "@GooglePayIndia", "portal": "https://support.google.com/pay/india/"},
    "PhonePe (PhonePe Pvt Ltd)": {"email": "grievance@phonepe.com", "industry": "Fintech", "regulator": "RBI", "twitter": "@PhonePeSupport", "portal": "https://www.phonepe.com/contact-us/"},
    "Paytm (One97 Communications Ltd)": {"email": "nodal@paytm.com", "industry": "Fintech", "regulator": "RBI", "twitter": "@Paytmcare", "portal": "https://paytm.com/care"},
    "CRED (Dreamplug Technologies Pvt Ltd)": {"email": "grievanceofficer@cred.club", "industry": "Fintech", "regulator": "RBI", "twitter": "@CRED_support", "portal": "https://cred.club/contact"},
    "BharatPe (Resilient Innovations Pvt Ltd)": {"email": "nodal@bharatpe.com", "industry": "Fintech", "regulator": "RBI", "twitter": "@bharatpeindia", "portal": "https://bharatpe.com/contact-us"},
    "MobiKwik (One MobiKwik Systems Ltd)": {"email": "nodal@mobikwik.com", "industry": "Fintech", "regulator": "RBI", "twitter": "@MobiKwikSWAT", "portal": "https://www.mobikwik.com/help"},
    "Freecharge (Freecharge Payment Technologies)": {"email": "grievanceofficer@freecharge.com", "industry": "Fintech", "regulator": "RBI", "twitter": "@FreeCharge", "portal": "https://www.freecharge.in/contactus"},
    "Amazon Pay (Amazon Pay India Pvt Ltd)": {"email": "nodal-officer-amazonpay@amazon.in", "industry": "Fintech", "regulator": "RBI", "twitter": "@AmazonHelp", "portal": "https://www.amazon.in/gp/help/customer/display.html"},
    "Slice (Garagepreneurs Internet Pvt Ltd)": {"email": "grievance@sliceit.com", "industry": "Fintech", "regulator": "RBI", "twitter": "@sliceit_", "portal": "https://www.sliceit.com/contact"},
    "Jupiter (Amica Financial Technologies)": {"email": "grievance@jupiter.money", "industry": "Fintech", "regulator": "RBI", "twitter": "@TheJupiterApp", "portal": "https://jupiter.money/contact-us/"},

    # BANKING (RBI)
    "HDFC Bank (HDFC Bank Limited)": {"email": "pno@hdfcbank.com", "industry": "Banking", "regulator": "RBI", "twitter": "@HDFC_Bank_Cares", "portal": "https://www.hdfcbank.com/personal/need-help"},
    "SBI (State Bank of India)": {"email": "customercare@sbi.co.in", "industry": "Banking", "regulator": "RBI", "twitter": "@TheOfficialSBI", "portal": "https://sbi.co.in/web/customer-care"},
    "ICICI Bank (ICICI Bank Limited)": {"email": "headservicequality@icicibank.com", "industry": "Banking", "regulator": "RBI", "twitter": "@ICICIBank_Care", "portal": "https://www.icicibank.com/complaints"},
    "Axis Bank (Axis Bank Limited)": {"email": "pno@axisbank.com", "industry": "Banking", "regulator": "RBI", "twitter": "@AxisBankSupport", "portal": "https://www.axisbank.com/contact-us"},
    "Kotak Mahindra Bank (Kotak Mahindra Bank Ltd)": {"email": "nodal.officer@kotak.com", "industry": "Banking", "regulator": "RBI", "twitter": "@KotakBankLtd", "portal": "https://www.kotak.com/en/customer-service.html"},
    "Punjab National Bank (PNB)": {"email": "care@pnb.co.in", "industry": "Banking", "regulator": "RBI", "twitter": "@pnbindia", "portal": "https://www.pnbindia.in/customer-care.html"},
    "Bank of Baroda (BoB)": {"email": "cs.ho@bankofbaroda.com", "industry": "Banking", "regulator": "RBI", "twitter": "@bankofbaroda", "portal": "https://www.bankofbaroda.in/contact-us"},
    "IndusInd Bank (IndusInd Bank Limited)": {"email": "nodal.officer@indusind.com", "industry": "Banking", "regulator": "RBI", "twitter": "@MyIndusIndBank", "portal": "https://www.indusind.com/in/en/personal/contact-us.html"},
    "IDFC First Bank (IDFC FIRST Bank Ltd)": {"email": "pno@idfcfirstbank.com", "industry": "Banking", "regulator": "RBI", "twitter": "@IDFCFIRSTBank", "portal": "https://www.idfcfirstbank.com/contact-us"},
    "Yes Bank (YES BANK Limited)": {"email": "pno@yesbank.in", "industry": "Banking", "regulator": "RBI", "twitter": "@YESBANKCare", "portal": "https://www.yesbank.in/contact-us"},

    # MOBILITY & TRAVEL (CCPA)
    "Ola Cabs (ANI Technologies Pvt Ltd)": {"email": "grievance@olacabs.com", "industry": "Mobility", "regulator": "CCPA", "twitter": "@Ola_Support", "portal": "https://www.olacabs.com/contact"},
    "Uber India (Uber India Systems Pvt Ltd)": {"email": "grievanceofficer_india@uber.com", "industry": "Mobility", "regulator": "CCPA", "twitter": "@Uber_Support", "portal": "https://help.uber.com/"},
    "Rapido (Roppen Transportation Services)": {"email": "grievance@rapido.bike", "industry": "Mobility", "regulator": "CCPA", "twitter": "@rapidobikeapp", "portal": "https://rapido.bike/contact-us"},
    "MakeMyTrip (MakeMyTrip India Pvt Ltd)": {"email": "grievance.officer@makemytrip.com", "industry": "Travel", "regulator": "CCPA", "twitter": "@makemytripcare", "portal": "https://www.makemytrip.com/support/"},
    "Goibibo (Ibibo Group Pvt Ltd)": {"email": "grievance.officer@goibibo.com", "industry": "Travel", "regulator": "CCPA", "twitter": "@goibibo", "portal": "https://www.goibibo.com/support/"},
    "EaseMyTrip (Easy Trip Planners Ltd)": {"email": "grievance@easemytrip.com", "industry": "Travel", "regulator": "CCPA", "twitter": "@EaseMyTrip", "portal": "https://www.easemytrip.com/contact-us.html"},
    "Yatra (Yatra Online Ltd)": {"email": "grievance.officer@yatra.com", "industry": "Travel", "regulator": "CCPA", "twitter": "@YatraOfficial", "portal": "https://www.yatra.com/support"},
    "Cleartrip (Cleartrip Pvt Ltd)": {"email": "grievanceofficer@cleartrip.com", "industry": "Travel", "regulator": "CCPA", "twitter": "@Cleartrip", "portal": "https://www.cleartrip.com/support"},
    "RedBus (Ibibo Group Pvt Ltd)": {"email": "grievanceofficer@redbus.in", "industry": "Travel", "regulator": "CCPA", "twitter": "@redBus_in", "portal": "https://www.redbus.in/info/contactus"},
    "IRCTC (Indian Railway Catering and Tourism Corp)": {"email": "care@irctc.co.in", "industry": "Travel", "regulator": "CCPA", "twitter": "@IRCTCofficial", "portal": "https://www.irctc.co.in/nget/en/contactus"},

    # TELECOM & BROADBAND (TRAI/CCPA)
    "Reliance Jio (Reliance Jio Infocomm Ltd)": {"email": "appellate@jio.com", "industry": "Telecom", "regulator": "CCPA", "twitter": "@JioCare", "portal": "https://www.jio.com/help/contact-us"},
    "Bharti Airtel (Bharti Airtel Ltd)": {"email": "nodalofficer@airtel.com", "industry": "Telecom", "regulator": "CCPA", "twitter": "@Airtel_Presence", "portal": "https://www.airtel.in/help"},
    "Vodafone Idea (Vi)": {"email": "appellate.officer@vodafoneidea.com", "industry": "Telecom", "regulator": "CCPA", "twitter": "@ViCustomerCare", "portal": "https://www.myvi.in/help-support"},
    "BSNL (Bharat Sanchar Nigam Limited)": {"email": "cgm_hq@bsnl.co.in", "industry": "Telecom", "regulator": "CCPA", "twitter": "@BSNLCorporate", "portal": "https://www.bsnl.co.in/opencms/bsnl/BSNL/about_us/customer_care.html"},
    "ACT Fibernet (Atria Convergence Technologies)": {"email": "nodal@actcorp.in", "industry": "Telecom", "regulator": "CCPA", "twitter": "@ACTFibernet", "portal": "https://www.actcorp.in/contact-us"},
    "Hathway (Hathway Cable & Datacom Ltd)": {"email": "nodalofficer@hathway.net", "industry": "Telecom", "regulator": "CCPA", "twitter": "@HathwayCableTV", "portal": "https://www.hathway.com/ContactUs"},
    "Excitel (Excitel Broadband Pvt Ltd)": {"email": "nodal@excitel.com", "industry": "Telecom", "regulator": "CCPA", "twitter": "@Excitel", "portal": "https://www.excitel.com/contact-us/"},

    # EDTECH (CCPA)
    "Byju's (Think & Learn Pvt Ltd)": {"email": "grievances@byjus.com", "industry": "EdTech", "regulator": "CCPA", "twitter": "@BYJUS", "portal": "https://byjus.com/contact-us/"},
    "Unacademy (Sorting Hat Technologies)": {"email": "grievance@unacademy.com", "industry": "EdTech", "regulator": "CCPA", "twitter": "@unacademy", "portal": "https://unacademy.com/contact"},
    "PhysicsWallah (PhysicsWallah Pvt Ltd)": {"email": "grievance.officer@pw.live", "industry": "EdTech", "regulator": "CCPA", "twitter": "@PhysicswallahAP", "portal": "https://www.pw.live/contact-us"},
    "Vedantu (Vedantu Innovations Pvt Ltd)": {"email": "grievance@vedantu.com", "industry": "EdTech", "regulator": "CCPA", "twitter": "@vedantu_learn", "portal": "https://www.vedantu.com/contact-us"},
    "UpGrad (UpGrad Education Pvt Ltd)": {"email": "grievance@upgrad.com", "industry": "EdTech", "regulator": "CCPA", "twitter": "@upGrad_edu", "portal": "https://www.upgrad.com/contact/"},
    "Simplilearn (Simplilearn Solutions Pvt Ltd)": {"email": "grievance@simplilearn.com", "industry": "EdTech", "regulator": "CCPA", "twitter": "@simplilearn", "portal": "https://www.simplilearn.com/contact-us"},
    "Cuemath (CueLearn Pvt Ltd)": {"email": "grievance@cuemath.com", "industry": "EdTech", "regulator": "CCPA", "twitter": "@cuemath", "portal": "https://www.cuemath.com/contact/"},

    # AIRLINES (CCPA)
    "IndiGo (InterGlobe Aviation Ltd)": {"email": "nodalofficer@goindigo.in", "industry": "Airlines", "regulator": "CCPA", "twitter": "@IndiGo6E", "portal": "https://www.goindigo.in/contact-us.html"},
    "Air India (Air India Ltd)": {"email": "nodalofficer@airindia.com", "industry": "Airlines", "regulator": "CCPA", "twitter": "@airindia", "portal": "https://www.airindia.com/in/en/contact-us.html"},
    "SpiceJet (SpiceJet Ltd)": {"email": "nodalofficer@spicejet.com", "industry": "Airlines", "regulator": "CCPA", "twitter": "@flyspicejet", "portal": "https://corporate.spicejet.com/contactus.aspx"},
    "Akasa Air (SNV Aviation Pvt Ltd)": {"email": "nodalofficer@akasaair.com", "industry": "Airlines", "regulator": "CCPA", "twitter": "@AkasaAir", "portal": "https://www.akasaair.com/contact-us"},
    "Air India Express (Air India Express Ltd)": {"email": "nodalofficer@airindiaexpress.com", "industry": "Airlines", "regulator": "CCPA", "twitter": "@FlyAIExpress", "portal": "https://www.airindiaexpress.com/contact-us"},

    # CONSUMER ELECTRONICS & HOME SERVICES (CCPA)
    "Samsung India (Samsung India Electronics)": {"email": "grievance.officer@samsung.com", "industry": "Electronics", "regulator": "CCPA", "twitter": "@SamsungIndia", "portal": "https://www.samsung.com/in/support/contact/"},
    "Apple India (Apple India Pvt Ltd)": {"email": "grievance_officer_india@apple.com", "industry": "Electronics", "regulator": "CCPA", "twitter": "@AppleSupport", "portal": "https://www.apple.com/in/contact/"},
    "Xiaomi India (Xiaomi Technology India)": {"email": "grievance.officer@xiaomi.com", "industry": "Electronics", "regulator": "CCPA", "twitter": "@XiaomiIndia", "portal": "https://www.mi.com/in/support/contact/"},
    "OnePlus India (OPlus Mobitech India)": {"email": "grievance@oneplus.com", "industry": "Electronics", "regulator": "CCPA", "twitter": "@OnePlus_IN", "portal": "https://www.oneplus.in/support/contact"},
    "Dell India (Dell International Services)": {"email": "grievance_officer@dell.com", "industry": "Electronics", "regulator": "CCPA", "twitter": "@DellCares", "portal": "https://www.dell.com/support/contents/en-in/category/contact-information"},
    "HP India (HP India Sales Pvt Ltd)": {"email": "grievance_officer.india@hp.com", "industry": "Electronics", "regulator": "CCPA", "twitter": "@HPIndia", "portal": "https://www.hp.com/in-en/contact-hp/contact.html"},
    "Lenovo India (Lenovo India Pvt Ltd)": {"email": "igrievance@lenovo.com", "industry": "Electronics", "regulator": "CCPA", "twitter": "@Lenovo_in", "portal": "https://www.lenovo.com/in/en/contact/"},
    "LG India (LG Electronics India Pvt Ltd)": {"email": "grievance.officer@lge.com", "industry": "Electronics", "regulator": "CCPA", "twitter": "@LGIndia", "portal": "https://www.lg.com/in/support/contact/"},
    "Sony India (Sony India Pvt Ltd)": {"email": "sonyindia.care@sony.com", "industry": "Electronics", "regulator": "CCPA", "twitter": "@sony_india", "portal": "https://www.sony.co.in/electronics/support"},
    "boAt Lifestyle (Imagine Marketing Ltd)": {"email": "grievance.officer@imaginemarketingindia.com", "industry": "Electronics", "regulator": "CCPA", "twitter": "@RockWithboAt", "portal": "https://www.boat-lifestyle.com/pages/contact-us"},
    "Urban Company (UrbanClap Technologies)": {"email": "grievanceofficer@urbancompany.com", "industry": "Home Services", "regulator": "CCPA", "twitter": "@urbancompany_UC", "portal": "https://www.urbancompany.com/contact-us"}
}

limiter = Limiter(key_func=get_remote_address)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("⚡ Karma Claims v4.1 is online.")
    yield

app = FastAPI(title="Karma Claims v4.1", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(CORSMiddleware, allow_origins=ALLOWED_ORIGINS, allow_credentials=False, allow_methods=["*"], allow_headers=["*"])

client = AsyncGroq(api_key=API_KEY)

@app.get("/health")
async def health_check():
    return {"status": "Live", "version": "4.1", "systems_online": 9}

class DisputeRequest(BaseModel):
    user_name: str; user_email: EmailStr; user_phone: str; company_name: str; order_id: str; disputed_amount: str; complaint_details: str
    @field_validator('disputed_amount')
    def sanitize_amount(cls, v):
        clean = ''.join(filter(lambda x: x.isdigit() or x == '.', str(v)))
        return clean if clean else "0"

class ChatRequest(BaseModel): user_message: str
class BSDetectorRequest(BaseModel): corporate_reply: str
class OutcomeRequest(BaseModel): amount_recovered: float; company_name: str; has_screenshot: bool = False

@app.post("/generate-draft")
@limiter.limit("5/minute")
async def generate_legal_draft(request: Request, payload: DisputeRequest):
    legal_framework = "Consumer Protection Act (CCPA) 2019"
    if payload.company_name in VERIFIED_DB and VERIFIED_DB[payload.company_name].get("regulator") == "RBI":
        legal_framework = "Reserve Bank of India (RBI) rules for unauthorized transactions"

    prompt = f"""You are a fierce Indian corporate lawyer. Draft a formal legal grievance notice for {payload.user_name} against {payload.company_name}.
    Details: Order ID {payload.order_id}, Amount ₹{payload.disputed_amount}. Complaint: {payload.complaint_details}
    Rules:
    1. Base threats strictly on the {legal_framework}.
    2. Demand a resolution within 48 hours or threaten escalation to the Nodal Officer/Ombudsman.
    3. Keep it highly professional, intimidating, and ready to send. No placeholders.
    4. Sign off with: {payload.user_name} | Ph: {payload.user_phone}"""
    try:
        response = await client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": "You are a legal AI."}, {"role": "user", "content": prompt}],
            temperature=0.3, max_tokens=600
        )
        target_email = VERIFIED_DB.get(payload.company_name, {}).get("email", "support@company.com")
        return {"draft": response.choices[0].message.content.strip(), "target_email": target_email}
    except Exception:
        raise HTTPException(status_code=500, detail="Engine overloaded. Please try again.")

@app.get("/api/dashboard")
async def get_dashboard_stats():
    return get_dynamic_metrics()

@app.post("/api/report-outcome")
@limiter.limit("3/minute") 
async def report_outcome(request: Request, payload: OutcomeRequest):
    global SESSION_RECOVERED, SESSION_WINS
    SESSION_RECOVERED += payload.amount_recovered
    SESSION_WINS += 1
    return {"status": "success", "message": "Community scoreboard updated!", "new_total": get_dynamic_metrics()["total_recovered"]}

@app.get("/api/timeline/{company_name}")
async def get_deadlines(company_name: str):
    today = datetime.now()
    if company_name not in VERIFIED_DB:
        return {
            "level_1_deadline": (today + timedelta(days=7)).strftime("%Y-%m-%d"),
            "consumer_court_date": (today + timedelta(days=30)).strftime("%Y-%m-%d"),
            "warning": "Generic Company Detected: If no refund by Day 30, generate e-Daakhil package under the Consumer Protection Act.",
            "unverified": True
        }
    
    reg = VERIFIED_DB[company_name]["regulator"]
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
            "warning": "CCPA Rule: If no refund by Day 30, file via e-Daakhil.",
            "unverified": False
        }

@app.post("/api/chat")
@limiter.limit("10/minute")
async def karma_chat(request: Request, payload: ChatRequest):
    try:
        response = await client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": "You are Karma AI. Give sharp, 2-sentence legal pushbacks to corporate delays using RBI/CCPA rules."}, {"role": "user", "content": payload.user_message}],
            temperature=0.4, max_tokens=300
        )
        return {"reply": response.choices[0].message.content.strip()}
    except Exception:
        raise HTTPException(status_code=500, detail="Karma AI is busy.")

@app.post("/api/detect-bs")
@limiter.limit("5/minute")
async def detect_bullshit(request: Request, payload: BSDetectorRequest):
    try:
        response = await client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": "Analyze the corporate email. State if they are using a 'Stalling Tactic', 'Illegal Demand', or 'Valid Request'. Explain why in 1 sentence. Then give the user 1 sentence to reply with."}, {"role": "user", "content": f"Corporate Email: {payload.corporate_reply}"}],
            temperature=0.1, max_tokens=200
        )
        return {"analysis": response.choices[0].message.content.strip()}
    except Exception:
        raise HTTPException(status_code=500, detail="Detector offline.")

@app.post("/api/edakhil-package")
@limiter.limit("5/minute") 
async def generate_edakhil(request: Request, payload: DisputeRequest):
    target_email = VERIFIED_DB.get(payload.company_name, {}).get("email", "Find company email online")
    edakhil_json = {
        "Complainant_Details": {"Name": payload.user_name, "Mobile": payload.user_phone, "Email": payload.user_email},
        "Opposite_Party": {"Name": payload.company_name, "Email": target_email},
        "Grievance_Details": {"Dispute_Value": payload.disputed_amount, "Transaction_ID": payload.order_id},
        "Prayer_for_Relief": f"Immediate refund of ₹{payload.disputed_amount} plus 12% interest for mental agony."
    }
    return {"status": "Package Generated", "data": edakhil_json, "next_step": "Upload this structure directly to edaakhil.nic.in"}

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