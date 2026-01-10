import os
import json
import asyncio
import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import google.generativeai as genai

# --- CUSTOM MODULES ---
PLAYWRIGHT_AVAILABLE = True

# Debug: show cwd and top-level files when imports fail
def _debug_import_env(module_name: str, exc: Exception):
    try:
        cwd = os.getcwd()
        files = []
        try:
            files = os.listdir('.')
        except Exception as _:
            pass
        print(f"⚠️ IMPORT DEBUG: Failed to import {module_name}. CWD={cwd}. Files={files[:20]}")
        print(f"⚠️ IMPORT ERROR: {type(exc).__name__}: {exc}")
    except Exception as _:
        pass

try:
    from price_hunter import PriceHunter
except Exception as e:
    _debug_import_env('price_hunter', e)
    print("⚠️ WARNING: price_hunter.py not loaded. Market scanning disabled.")
    PriceHunter = None
    PLAYWRIGHT_AVAILABLE = False

try:
    from history_hunter import HistoryHunter
except Exception as e:
    _debug_import_env('history_hunter', e)
    print("⚠️ WARNING: history_hunter.py not loaded. History check disabled.")
    HistoryHunter = None
    PLAYWRIGHT_AVAILABLE = False

load_dotenv()

app = FastAPI(title="ZIVA: Commerce Intelligence Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize AI Client
api_key = os.getenv("GEMINI_API_KEY")
model = None

if api_key:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('models/gemma-3-27b-it')  # Same as extension
    print("🧠 AI CORTEX: Connected (Gemma 3 27B IT)")
else:
    print("⚠️ AI CORTEX: OFFLINE (Missing GEMINI_API_KEY)")


def extract_product_title(url):
    """Extract product title and price from Amazon/Flipkart URL"""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.content, "html.parser")
        
        # Try Amazon title
        title_tag = soup.find("span", {"id": "productTitle"})
        current_price = 0
        
        if title_tag:
            # Extract current price from Amazon
            price_tag = soup.find("span", {"class": "a-price-whole"})
            if price_tag:
                try:
                    price_text = price_tag.get_text().replace("₹", "").replace(",", "").strip()
                    current_price = int(float(price_text.split(".")[0]))
                except:
                    pass
            
            full_title = title_tag.get_text().strip()
            print(f"✅ Extracted: {full_title[:80]}... @ ₹{current_price}")
            return full_title, current_price
        
        # Try Flipkart/Croma title
        title_tag = soup.find("h1")
        if title_tag:
            full_title = title_tag.get_text().strip()
            print(f"✅ Extracted: {full_title[:80]}...")
            return full_title, current_price
        
        # Fallback: extract from URL
        if "amazon" in url.lower():
            title = url.split("/dp/")[0].split("/")[-1]
            fallback_title = title.replace("-", " ") if title else "Unknown Product"
            print(f"⚠️ Fallback URL-based title: {fallback_title}")
            return fallback_title, current_price
        
        print("⚠️ Could not extract title from page")
        return "Unknown Product", current_price
    except Exception as e:
        print(f"❌ Title/Price extraction failed: {e}")
        return "Unknown Product", 0


@app.get("/")
def home():
    return {"status": "Ziva Intelligence System Online ⚡", "modules": ["AI", "Market", "History"]}


@app.post("/scan")
async def scan_endpoint(request_data: dict):
    """Main API endpoint for URL scanning"""
    if 'url' not in request_data:
        return {"error": "No URL provided"}
    
    url = request_data['url']
    
    # Extract product title and current price from URL
    product_title, current_price = extract_product_title(url)
    print(f"\n🔎 STARTING INVESTIGATION: {product_title} | Current Price: ₹{current_price}")
    
    # --- STEP 1: PARALLEL EXECUTION ---
    # We launch 3 tasks: AI Analysis, Price Hunt, History Hunt
    
    # Task A: AI
    ai_task = asyncio.create_task(run_ai_analysis(product_title))
    
    # Task B: Market Scanner (Flipkart, Croma)
    hunter_task = None
    if PriceHunter:
        hunter = PriceHunter()
        hunter_task = asyncio.create_task(hunter.hunt(product_title))

    # Task C: Price History
    history_task = None
    if HistoryHunter:
        historian = HistoryHunter()
        history_task = asyncio.create_task(historian.get_history(product_title))
    
    # --- STEP 2: GATHER RESULTS ---
    # We wait for AI (Critical)
    ai_result = await ai_task
    
    # We wait for others (Optional)
    competitor_data = []
    if hunter_task:
        try:
            competitor_data = await asyncio.wait_for(hunter_task, timeout=40)
        except asyncio.TimeoutError:
            print(f"⚠️ TIMEOUT: Market Scanner took too long (>40s)")
            competitor_data = []
        except Exception as e:
            print(f"❌ Market Scanner Error: {e}")
            competitor_data = []
        
    history_data = None
    if history_task:
        try:
            history_data = await asyncio.wait_for(history_task, timeout=40)
        except asyncio.TimeoutError:
            print(f"⚠️ TIMEOUT: Price History took too long (>40s)")
            history_data = None
        except Exception as e:
            print(f"❌ Price History Error: {e}")
            history_data = None

    # --- STEP 3: SYNTHESIS ---
    final_response = ai_result
    final_response["competitors"] = competitor_data if competitor_data else []
    final_response["history"] = history_data
    final_response["current_price"] = current_price  # Send current price to frontend
    
    # Logic: Check for savings
    if competitor_data:
        best_deal = min(competitor_data, key=lambda x: x['price'])
        
        final_response["market_intel"] = {
            "best_price": best_deal['price'],
            "best_site": best_deal['site'],
            "link": best_deal['link']
        }
        # Add alert to reason text
        final_response["reason"] += f" (Found on {best_deal['site']} for ₹{best_deal['price']:,})"

    print(f"✅ REPORT GENERATED: {final_response.get('verdict', 'UNKNOWN')}")
    return final_response


async def run_ai_analysis(product_title: str):
    """AI Analysis Task"""
    default_response = {
        "verdict": "UNKNOWN", "score": 50, "reason": "AI currently unavailable."
    }
    if not model: 
        return default_response

    prompt = f"""
    Act as Ziva, a fraud detection AI.
    Product: "{product_title}"
    
    RULES:
    1. TRUST THE REVIEW COUNT: If a product has reviews on Amazon, it is RELEASED.
    2. IGNORE your training data cutoff regarding release dates.
    3. FOCUS ONLY ON SCAMS: Look for "16TB SSD for $20" or gibberish brand names.
    4. If the specs look realistic for the price, verdict is SAFE.
    
    Respond in this format: VERDICT | REASON
    Example: SAFE | Specs match price and high review count confirms authenticity.
    Example: SUSPICIOUS | Generic brand name with impossible specs.
    """

    try:
        response = await asyncio.to_thread(model.generate_content, prompt)
        text = response.text.strip()
        
        verdict = "SAFE"
        reason = "Verified."
        score = 90

        if "|" in text:
            parts = text.split("|", 1)
            verdict_raw = parts[0].strip().upper()
            reason_raw = parts[1].strip()
            
            if "SAFE" in verdict_raw:
                verdict = "SAFE"; score = 90
            elif "SUSPICIOUS" in verdict_raw:
                verdict = "SUSPICIOUS"; score = 40
            
            reason = reason_raw

        return {"verdict": verdict, "score": score, "reason": reason}

    except Exception as e:
        print(f"❌ AI Error: {e}")
        return default_response


if __name__ == '__main__':
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
