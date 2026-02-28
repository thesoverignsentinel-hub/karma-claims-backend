import os
import time
import httpx
import PyPDF2
from dotenv import load_dotenv
from supabase import create_client

# --- SETUP ---
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
HF_TOKEN = os.getenv("HF_TOKEN")

if not all([SUPABASE_URL, SUPABASE_KEY, HF_TOKEN]):
    print("❌ ERROR: Missing credentials in .env file (SUPABASE_URL, SUPABASE_KEY, HF_TOKEN).")
    exit()

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
# Using the all-MiniLM-L6-v2 model for fast, high-quality legal embeddings
hf_api_url = "https://router.huggingface.co/hf-inference/models/sentence-transformers/all-MiniLM-L6-v2/pipeline/feature-extraction"
headers = {"Authorization": f"Bearer {HF_TOKEN}"}

# --- THE 100% SPECIFIC 1-TO-1 TAGGING SYSTEM ---
def get_metadata_for_file(filename):
    name = filename.lower()
    
    # 🏦 BANKING & FINANCE (Including 2026 Updates)
    if "ombudsman_2026" in name:
        return {
            "industry": "Banking", 
            "act": "RBI Integrated Ombudsman Scheme 2026", 
            "penalty": "₹30 Lakhs for financial loss + ₹3 Lakhs for mental agony (Effective July 2026)"
        }
    elif "rbi_tat_framework" in name:
        return {"industry": "Banking", "act": "RBI TAT Framework 2019", "penalty": "₹100 per day for delay beyond T+1"}
    elif "rbi_compensation_policy" in name:
        return {"industry": "Banking", "act": "RBI Compensation Policy", "penalty": "Mandatory compensation for failed banking services"}
    elif "rbi_zero_customer_liability" in name:
        return {"industry": "Banking", "act": "RBI Zero Customer Liability", "penalty": "Full refund for unauthorized transactions if reported within 3 days"}
    elif "rbi_digital_payment_security" in name:
        return {"industry": "Banking", "act": "RBI Digital Payment Security Controls", "penalty": "Bank liability for security compliance failures"}
    elif "rbi_ombudsman_scheme" in name: # 2021 Version
        return {"industry": "Banking", "act": "RBI Integrated Ombudsman Scheme 2021", "penalty": "Binding resolution and compensation up to ₹20 Lakhs"}

    # ✈️ AVIATION & TRANSPORT
    elif "dgca_car_refund" in name:
        return {"industry": "Aviation", "act": "DGCA CAR Refund Rules", "penalty": "Immediate full refund for cancelled tickets"}
    elif "dgca_car_section_3" in name:
        return {"industry": "Aviation", "act": "DGCA CAR Section 3", "penalty": "Up to ₹10,000 compensation for cancellation or denied boarding"}
    elif "morth" in name:
        return {"industry": "Transport", "act": "MoRTH Cab Aggregator Guidelines", "penalty": "Cap on surge pricing and maximum cancellation fee limits"}

    # 📱 TELECOM
    elif "trai_telecom_redressal" in name:
        return {"industry": "Telecom", "act": "TRAI Consumer Complaint Redressal", "penalty": "Mandatory grievance resolution and billing corrections"}
    elif "trai_telecom_regulatory" in name:
        return {"industry": "Telecom", "act": "TRAI Regulatory Rules 2006", "penalty": "Financial disincentives for network operators"}
    elif "trai_quality_of_service" in name:
        return {"industry": "Telecom", "act": "TRAI Quality of Service 2019", "penalty": "Compensation for service disruption or dropping calls"}

    # 🛒 E-COMMERCE & CONSUMER RIGHTS
    elif "ecommerce_rules_2020" in name:
        return {"industry": "E-Commerce", "act": "Consumer Protection (E-Commerce) Rules 2020", "penalty": "Mandatory refund for defective/counterfeit goods"}
    elif "ccpa_dark_patterns" in name:
        return {"industry": "Consumer Rights", "act": "CCPA Dark Patterns Guidelines 2023", "penalty": "Strict penalty for misleading UI/UX (e.g., forced subscriptions)"}
    elif "ccpa_misleading_ads" in name:
        return {"industry": "Consumer Rights", "act": "CCPA Misleading Ads Guidelines", "penalty": "Fines up to ₹10 Lakhs for false advertising"}
    elif "consumer_protection_act_2019" in name:
        return {"industry": "General Legal", "act": "Consumer Protection Act 2019", "penalty": "Compensation for Deficiency in Service and Unfair Trade Practices"}

    # ⚖️ CYBER LAW & RAILWAYS
    elif "it_act_intermediary" in name:
        return {"industry": "Cyber Law", "act": "IT Act Intermediary Guidelines 2021", "penalty": "Loss of safe harbour & mandatory account reinstatement"}
    elif "it_act_2000" in name:
        return {"industry": "Cyber Law", "act": "Information Technology Act 2000", "penalty": "Compensation for data breach and cyber fraud"}
    elif "railway" in name:
        return {"industry": "Railways", "act": "Railway Passengers (Cancellation/Refund) Rules", "penalty": "Mandatory refund of ticket fare"}

    # 🛡️ SMART FALLBACK
    else:
        clean_name = filename.replace(".pdf", "").replace("_", " ").title()
        return {"industry": "General Legal", "act": clean_name, "penalty": "Deficiency in Service compensation (CPA 2019)"}

# --- THE IMPENETRABLE NETWORK FORTRESS ---
def get_math_vector_safely(chunk_text):
    for attempt in range(10): # High retry count for stability
        try:
            response = httpx.post(hf_api_url, headers=headers, json={"inputs": chunk_text}, timeout=20.0)
            
            if response.status_code == 200:
                vector = response.json()
                if isinstance(vector, list) and len(vector) > 0 and isinstance(vector[0], list):
                    return vector[0]
                return vector
            elif response.status_code == 429:
                print(f"      [Wait] HF API rate limited. Pausing 10s...")
                time.sleep(10)
            else:
                print(f"      [Error] API {response.status_code}. Retrying...")
                time.sleep(5)
                
        except Exception as e:
            print(f"      [Shock Absorbed] Connection blip: {type(e).__name__}. Retrying...")
            time.sleep(5)
            
    return None

# --- MAIN INGESTION LOGIC ---
def process_pdfs():
    pdf_folder = "karma_legal_brain" 
    
    if not os.path.exists(pdf_folder):
        print(f"❌ ERROR: Cannot find the folder '{pdf_folder}'. Create it and add your PDFs.")
        return

    files = [f for f in os.listdir(pdf_folder) if f.endswith(".pdf")]
    print(f"🚀 Starting Ingestion for {len(files)} files...")

    for filename in files:
        print(f"\n📄 Processing: {filename}")
        metadata = get_metadata_for_file(filename)
        print(f"🏷️  Tag: {metadata['act']} | Weapon: {metadata['penalty']}")

        file_path = os.path.join(pdf_folder, filename)
        try:
            with open(file_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                text = ""
                for page in reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
        except Exception as e:
            print(f"⚠️ Could not read {filename}: {e}")
            continue

        # Split into 800-character chunks for optimal AI search
        chunks = [text[i:i+800] for i in range(0, len(text), 800)]
        print(f"✂️  Uploading {len(chunks)} chunks to Supabase...")

        for index, chunk in enumerate(chunks):
            if len(chunk.strip()) < 50:
                continue 
            
            vector = get_math_vector_safely(chunk)
            
            if vector:
                try:
                    data = {
                        "industry_category": metadata["industry"],
                        "act_name": metadata["act"],
                        "specific_penalty": metadata["penalty"],
                        "content": chunk,
                        "embedding": vector
                    }
                    supabase.table("legal_documents_v2").insert(data).execute()
                except Exception as db_error:
                    print(f"   ❌ DB Error: {db_error}")
            
            # 2-second delay to stay within Hugging Face free tier limits
            time.sleep(2)

    print("\n🎉 MISSION COMPLETE! V2 Database is fully loaded and 2026-Ready.")

if __name__ == "__main__":
    process_pdfs()