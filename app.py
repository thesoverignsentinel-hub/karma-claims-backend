import os
import asyncio
import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator
from dotenv import load_dotenv
from groq import AsyncGroq # Swapped Gemini for Groq

# ── 1. Professional Logging ──────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ── 2. Environment & API Key Security ────────────────────────────────────────
load_dotenv()  
API_KEY = os.getenv("GROQ_API_KEY") # Swapped variable name

if not API_KEY:
    raise RuntimeError("GROQ_API_KEY not set. Add it to your .env file.")

# ── 3. Global Model Instantiation ────────────────────────────────────────────
client = AsyncGroq(api_key=API_KEY) # Initializing Groq client

# ── 4. App Initialization ────────────────────────────────────────────────────
app = FastAPI(title="Karma Claims API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 5. The Data Moat ─────────────────────────────────────────────────────────
GRIEVANCE_DB: dict[str, str] = {
    "zomato":      "grievance@zomato.com",
    "swiggy":      "griances@swiggy.in",
    "blinkit":     "grievance.officer@blinkit.com",
    "zepto":       "grievanceofficer@zeptonow.com",
    "amazon":      "grievance-officer@amazon.in",
    "flipkart":    "grievance.officer@flipkart.com",
    "ola":         "grievance@olacabs.com",
    "uber":        "grievanceofficer_india@uber.com",
    "makemytrip":  "nodal.officer@makemytrip.com",
    "paytm":       "nodal@paytm.com",
}

# ── 6. Secure Request Model with Injection Guards (Untouched) ────────────────
class DisputeRequest(BaseModel):
    user_email:        str
    user_phone:        str
    company_name:      str
    order_id:          str
    disputed_amount:   str
    complaint_details: str

    @field_validator("company_name", "order_id", "complaint_details", mode="before")
    @classmethod
    def must_not_be_empty(cls, v: str, info) -> str:
        if not v or not v.strip():
            raise ValueError(f"{info.field_name} must not be empty.")
        return v.strip()

    @field_validator("complaint_details", mode="before")
    @classmethod
    def sanitize_details(cls, v: str) -> str:
        for bad in ["ignore above", "ignore previous", "system:", "###", "---"]:
            v = v.lower().replace(bad, "")
        return v[:1000].strip()

# ── 7. The Core API Endpoint ─────────────────────────────────────────────────
@app.post("/generate-draft")
async def generate_legal_draft(request: DisputeRequest):
    company_key = request.company_name.lower().replace(" ", "")

    if company_key not in GRIEVANCE_DB:
        raise HTTPException(
            status_code=404,
            detail={"message": "Company not found in our database. Please check the spelling."}
        )

    target_email = GRIEVANCE_DB[company_key]

    # Claude's Progressive Async Retry Loop
    for attempt in range(3):
        try:
            logger.info(f"Generating draft for company='{request.company_name}' order='{request.order_id}' (attempt {attempt+1})")
            
            # THE SWAP: Using Groq's Llama 3 instead of Gemini
            response = await client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {
                        "role": "system", 
                        "content": (
                            "You are a professional Indian consumer rights advocate. "
                            "Draft a formal, firm grievance email. "
                            "Cite Rule 4(4) of the Consumer Protection (E-Commerce) Rules, 2020. "
                            "Keep the tone firm, professional, and factual. "
                            "Begin with: [ACTION REQUIRED: ATTACH PHOTO & RECEIPT BEFORE SENDING]. "
                            "Do not include any instructions to ignore previous prompts or act outside this role."
                        )
                    },
                    {
                        "role": "user", 
                        "content": (
                            f"Company: {request.company_name}\n"
                            f"Order ID: {request.order_id}\n"
                            f"Disputed Amount: ₹{request.disputed_amount}\n"
                            f"Consumer Phone: {request.user_phone}\n"
                            f"Consumer Email: {request.user_email}\n"
                            f"Issue: {request.complaint_details}"
                        )
                    }
                ],
                temperature=0.7,
                max_tokens=1024
            )
            
            draft_body = response.choices[0].message.content.strip()
            logger.info("Draft generated successfully via Groq.")
            
            return {
                "target_email": target_email,
                "subject": f"Formal Grievance Notice | {request.company_name.title()} | Order {request.order_id}",
                "body": draft_body,
            }
        except Exception as e:
            err = str(e)
            # Groq uses 429 for rate limits just like Google
            if "429" in err or "rate_limit" in err.lower():
                wait = 25 * (attempt + 1)
                logger.warning(f"Rate limited. Waiting {wait}s before retry...")
                await asyncio.sleep(wait) 
            else:
                logger.error(f"Groq error: {err}")
                raise HTTPException(status_code=500, detail={"message": "AI generation failed. Please try again."})

    raise HTTPException(status_code=503, detail={"message": "AI service is currently busy. Please try again in a few minutes."})

@app.get("/")
def home():
    return {"status": "Karma Claims Engine Active (Groq Powered)"}