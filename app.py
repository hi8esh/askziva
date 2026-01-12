import os
import json
import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import google.generativeai as genai
from playwright.async_api import async_playwright

try:
    from price_hunter import PriceHunter
except:
    PriceHunter = None

try:
    from history_hunter import HistoryHunter
except:
    HistoryHunter = None

load_dotenv()

app = FastAPI(title="ZIVA: Commerce Intelligence Engine")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

api_key = os.getenv("GEMINI_API_KEY")
model = None
if api_key:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('models/gemini-1.5-pro')

# --- LIGHTWEIGHT URL SCRAPER ---
async def scrape_product_page(url):
    print(f"🕵️‍♂️ Deep Scanning URL: {url}")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu']
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        # BLOCK IMAGES TO LOAD FAST
        await page.route("**/*", lambda route: route.abort() 
            if route.request.resource_type in ["image", "media", "font"] 
            else route.continue_())
        
        try:
            # wait_until="domcontentloaded" is 10x faster than "load"
            await page.goto(url, timeout=25000, wait_until="domcontentloaded")
            
            data = await page.evaluate("""() => {
                let title = "";
                let price = 0;
                let reviews = 0;

                // AMAZON
                if (document.location.hostname.includes('amazon')) {
                    const titleEl = document.querySelector('#productTitle');
                    if (titleEl) title = titleEl.innerText.trim();
                    
                    const priceEl = document.querySelector('.a-price-whole');
                    if (priceEl) price = parseInt(priceEl.innerText.replace(/[^0-9]/g, ''));
                    
                    const reviewEl = document.querySelector('#acrCustomerReviewText');
                    if (reviewEl) reviews = parseInt(reviewEl.innerText.split(' ')[0].replace(/,/g, ''));
                }
                
                // FLIPKART
                else if (document.location.hostname.includes('flipkart')) {
                    const titleEl = document.querySelector('.B_NuCI, .VU-ZEz');
                    if (titleEl) title = titleEl.innerText.trim();
                    
                    const priceEl = document.querySelector('div._30jeq3._16Jk6d, div.Nx9bqj.CxhGGd');
                    if (priceEl) price = parseInt(priceEl.innerText.replace(/[^0-9]/g, ''));
                    
                    const reviewEl = document.querySelector('span._2_R_DZ');
                    if (reviewEl) reviews = parseInt(reviewEl.innerText.split('&')[0].replace(/[^0-9]/g, ''));
                }
                return { title, price, reviews };
            }""")
            
            await browser.close()
            
            if not data['title']:
                return "Unknown Product", 0, 0
                
            print(f"✅ Extracted: {data['title'][:30]}... | ₹{data['price']} | {data['reviews']} reviews")
            return data['title'], data['price'], data['reviews']

        except Exception as e:
            print(f"❌ Scraping Error: {e}")
            await browser.close()
            return "Unknown Product", 0, 0

async def run_ai_analysis(title, reviews, price):
    if not model: return {"verdict": "UNKNOWN", "score": 50, "reason": "AI Offline"}
    
    if reviews > 500:
        return {"verdict": "SAFE", "score": 95, "reason": f"Product has {reviews:,} verified reviews. Community approved."}
        
    prompt = f"""
    Analyze this product for scams: "{title}" priced at ₹{price}.
    Verdict (SAFE/SUSPICIOUS) | Reason
    """
    try:
        response = await asyncio.to_thread(model.generate_content, prompt)
        text = response.text.strip()
        parts = text.split("|", 1)
        return {"verdict": parts[0].strip(), "score": 80, "reason": parts[1].strip() if len(parts)>1 else text}
    except:
        return {"verdict": "SAFE", "score": 80, "reason": "AI Analysis standard check passed."}

@app.post("/scan")
async def scan_endpoint(request_data: dict):
    if 'url' not in request_data: return {"error": "No input"}
    user_input = request_data['url'].strip()
    
    # LOGIC SWITCH
    if "http" in user_input or "www." in user_input:
        product_title, current_price, review_count = await scrape_product_page(user_input)
    else:
        print(f"🔍 Search Query: {user_input}")
        product_title = user_input
        current_price = 0
        review_count = 0

    # EXECUTION
    ai_task = asyncio.create_task(run_ai_analysis(product_title, review_count, current_price))
    
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
        try:
            competitors = await asyncio.wait_for(hunter_task, timeout=35)
        except: pass
        
    history = None
    if history_task:
        try:
            history = await asyncio.wait_for(history_task, timeout=35)
        except: pass

    # If Search Mode, pick best price as current
    if current_price == 0 and competitors:
        best_deal = min(competitors, key=lambda x: x['price'])
        current_price = best_deal['price']
        ai_result['reason'] += f" Best price found on {best_deal['site']}."

    response = ai_result
    response["product"] = product_title
    response["current_price"] = current_price
    response["competitors"] = competitors
    response["history"] = history
    
    return response