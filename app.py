import os
import asyncio
import re
import json
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import google.generativeai as genai
from playwright.async_api import async_playwright

# --- IMPORT HUNTERS ---
try:
    from price_hunter import PriceHunter
except ImportError:
    print("⚠️ WARNING: price_hunter.py not found. Market scanning disabled.")
    PriceHunter = None

try:
    from history_hunter import HistoryHunter
except ImportError:
    print("⚠️ WARNING: history_hunter.py not found. History check disabled.")
    HistoryHunter = None

try:
    from playwright_stealth import stealth_async as stealth_fn
except ImportError:
    async def stealth_fn(page): pass

load_dotenv()

app = FastAPI(title="ZIVA: Commerce Intelligence Engine")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- AI CONFIGURATION (From ziva-backend) ---
api_key = os.getenv("GEMINI_API_KEY")
model = None
if api_key:
    genai.configure(api_key=api_key)
    # Using the model from ziva-backend as it seems to be the preferred one for the logic
    model = genai.GenerativeModel('models/gemini-3-flash-preview')
    print("🧠 AI CORTEX: Connected (Gemini 3 flash)")
else:
    print("⚠️ AI CORTEX: OFFLINE (Missing GEMINI_API_KEY)")


# --- UTILS ---
def clean_title_for_search(title):
    if not title: return ""
    clean = re.split(r'[|(-]', title)[0].strip()
    words = clean.split()
    if len(words) > 4: return " ".join(words[:4])
    return clean

# --- CORE LOGIC: AI ANALYSIS (From ziva-backend) ---
async def run_ai_analysis(title: str, price=0, reviews=0):
    # Added price/reviews args to support the website's usage,
    # but the core logic will follow ziva-backend's prompt structure
    
    default_response = {
        "verdict": "UNKNOWN", "score": 50, "reason": "AI currently unavailable."
    }
    if not model: return default_response

    # Using the backend's prompt
    prompt = f"""
    Act as Ziva, a fraud detection AI.
    Product: "{title}"
    Price: {price}
    Reviews: {reviews}
    
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

# --- CORE LOGIC: SCRAPER (From app.py) ---
# Kept for the Website URL scanning feature
async def scrape_product_data(url):
    print(f"🕵️‍♂️ Deep Scanning URL: {url}")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-dev-shm-usage'])
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        await stealth_fn(page)
        
        await page.route("**/*", lambda route: route.abort() 
            if route.request.resource_type in ["image", "stylesheet", "font", "media"] 
            else route.continue_())
        
        try:
            await page.goto(url, timeout=30000, wait_until="commit")
            try: await page.wait_for_selector('body', timeout=5000) 
            except: pass
            
            data = await page.evaluate("""() => {
                let title = document.querySelector('meta[property="og:title"]')?.content || 
                            document.querySelector('meta[name="title"]')?.content || 
                            document.title;
                            
                let price = 0;
                const p1 = document.querySelector('.a-price-whole');
                if(p1) price = parseInt(p1.innerText.replace(/[^0-9]/g, ''));
                
                let reviews = 0;
                const r1 = document.querySelector('#acrCustomerReviewText');
                if(r1) reviews = parseInt(r1.innerText.split(' ')[0].replace(/,/g, ''));
                
                return { title, price, reviews };
            }""")
            
            await browser.close()
            return data['title'], data['price'], data['reviews']
        except Exception as e:
            print(f"❌ Scrape Error: {e}")
            await browser.close()
            return None, 0, 0

# --- ENDPOINTS ---

@app.get("/")
def home():
    return {"status": "Ziva Intelligence System Online ⚡", "modules": ["AI", "Market", "History"]}

# 1. EXTENSION ENDPOINT (From ziva-backend)
@app.get("/analyze")
async def analyze_product(title: str):
    print(f"\n🔎 [EXTENSION] INVESTIGATION: {title}")
    
    # Task A: AI
    ai_task = asyncio.create_task(run_ai_analysis(title))
    
    # Task B: Market Scanner
    hunter_task = None
    if PriceHunter:
        hunter = PriceHunter()
        hunter_task = asyncio.create_task(hunter.hunt(title)) # Use title directly, hunter cleans it

    # Task C: History
    history_task = None
    if HistoryHunter:
        historian = HistoryHunter()
        history_task = asyncio.create_task(historian.get_history(title))
    
    ai_result = await ai_task
    
    competitor_data = []
    if hunter_task:
        try: competitor_data = await hunter_task
        except: pass
        
    history_data = None
    if history_task:
        try: history_data = await history_task
        except: pass

    final_response = ai_result
    final_response["competitors"] = competitor_data or []
    final_response["history"] = history_data
    
    if competitor_data:
        best_deal = min(competitor_data, key=lambda x: x['price'])
        final_response["market_intel"] = {
            "best_price": best_deal['price'],
            "best_site": best_deal['site'],
            "link": best_deal['link']
        }

    return final_response

# 2. WEBSITE ENDPOINT (From app.py)
@app.post("/scan")
async def scan_endpoint(request_data: dict):
    if 'url' not in request_data: return {"error": "No input"}
    user_input = request_data['url'].strip()
    print(f"\nExample Scan: {user_input}")

    product_title = user_input
    current_price = 0
    review_count = 0

    if "http" in user_input or "www." in user_input:
        t, p, r = await scrape_product_data(user_input)
        if t: 
            product_title = t
            current_price = p
            review_count = r
    
    # Now delegate to the unified logic similar to /analyze but handling the response format 
    # expected by the website frontend (script.js)
    
    # NOTE: script.js expects: { verdict, score, reason, product, current_price, competitors, history }
    
    # I can actually call the same logic steps
    ai_task = asyncio.create_task(run_ai_analysis(product_title, current_price, review_count))
    
    search_term = clean_title_for_search(product_title)
    
    hunter_task = None
    if PriceHunter:
        hunter = PriceHunter()
        hunter_task = asyncio.create_task(hunter.hunt(product_title))

    history_task = None
    if HistoryHunter:
        historian = HistoryHunter()
        history_task = asyncio.create_task(historian.get_history(product_title))

    ai_result = await ai_task
    
    competitors = []
    if hunter_task:
        try: competitors = await hunter_task
        except: pass
        
    history = None
    if history_task:
        try: history = await history_task
        except: pass

    # Frontend Logic for "Current Price" vs "Competitors"
    if "http" in user_input and current_price > 0:
         # Add the scratched link as a "competitor" (current store)
        competitors.insert(0, {
            "site": "This Link",
            "title": "Current",
            "price": current_price,
            "link": user_input
        })

    return {
        "verdict": ai_result['verdict'],
        "score": ai_result['score'],
        "reason": ai_result['reason'],
        "product": product_title,
        "current_price": current_price,
        "competitors": competitors or [],
        "history": history
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)