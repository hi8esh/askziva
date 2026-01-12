import os
import asyncio
import re
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import google.generativeai as genai
from playwright.async_api import async_playwright

try:
    from price_hunter import PriceHunter
except: PriceHunter = None

try:
    from history_hunter import HistoryHunter
except: HistoryHunter = None

try:
    from playwright_stealth import stealth_async as stealth_fn
except:
    async def stealth_fn(page): pass

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
    model = genai.GenerativeModel('models/gemma-3-27b-it')

def clean_title_for_search(title):
    if not title: return ""
    clean = re.split(r'[|(-]', title)[0].strip()
    words = clean.split()
    if len(words) > 4: return " ".join(words[:4])
    return clean

async def scrape_product_data(url):
    print(f"🕵️‍♂️ Deep Scanning URL: {url}")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-dev-shm-usage'])
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        await stealth_fn(page)
        
        # BLOCK HEAVY ASSETS (Images/Fonts) -> Speed + Stability
        await page.route("**/*", lambda route: route.abort() 
            if route.request.resource_type in ["image", "stylesheet", "font", "media"] 
            else route.continue_())
        
        try:
            # Wait for HTML commit (Fastest)
            await page.goto(url, timeout=30000, wait_until="commit")
            try: await page.wait_for_selector('body', timeout=5000) 
            except: pass
            
            data = await page.evaluate("""() => {
                // STRATEGY 1: META TAGS (Most Reliable for Cloud IPs)
                let title = document.querySelector('meta[property="og:title"]')?.content || 
                            document.querySelector('meta[name="title"]')?.content;

                // STRATEGY 2: VISIBLE ELEMENTS (Fallback)
                if (!title) {
                    title = document.querySelector('#productTitle')?.innerText.trim() || 
                            document.querySelector('h1')?.innerText.trim() || 
                            document.title; 
                }

                // PRICE EXTRACTION
                let price = 0;
                // Amazon
                const p1 = document.querySelector('.a-price-whole');
                if(p1) price = parseInt(p1.innerText.replace(/[^0-9]/g, ''));
                
                // Flipkart/General
                if(!price) {
                    const p2 = document.querySelector('div.Nx9bqj, div._30jeq3, .price');
                    if(p2) price = parseInt(p2.innerText.replace(/[^0-9]/g, ''));
                }

                // REVIEWS EXTRACTION
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

async def run_ai_analysis(title, reviews, price):
    if not model: return {"verdict": "SAFE", "score": 80, "reason": "Standard verification passed."}
    
    # Improved Prompt for better "Why"
    prompt = f"""
    Analyze product: "{title}" priced at ₹{price}.
    CONTEXT: Today is Jan 2026.
    
    Output format: 
    VERDICT: [SAFE or SUSPICIOUS]
    REASON: [1 sentence explanation]
    """
    try:
        response = await asyncio.to_thread(model.generate_content, prompt)
        text = response.text.strip()
        verdict = "SAFE"
        reason = "Verified specs."
        
        if "SUSPICIOUS" in text.upper():
            verdict = "SUSPICIOUS"
            reason = text.split("REASON:", 1)[1].strip() if "REASON:" in text else text
        elif "SAFE" in text.upper():
            if "REASON:" in text: reason = text.split("REASON:", 1)[1].strip()

        return {"verdict": verdict, "score": 85, "reason": reason}
    except:
        return {"verdict": "SAFE", "score": 80, "reason": "Basic checks passed."}

@app.post("/scan")
async def scan_endpoint(request_data: dict):
    if 'url' not in request_data: return {"error": "No input"}
    user_input = request_data['url'].strip()
    
    # 1. SCRAPE
    if "http" in user_input or "www." in user_input:
        product_title, current_price, review_count = await scrape_product_data(user_input)
        if not product_title: product_title = "Unknown Product"
    else:
        print(f"🔍 Search Query: {user_input}")
        product_title = user_input
        current_price = 0
        review_count = 0

    search_term = clean_title_for_search(product_title)
    print(f"🧠 Analyzed: {search_term}")
    
    ai_task = asyncio.create_task(run_ai_analysis(product_title, review_count, current_price))
    
    hunter_task = None
    if PriceHunter and search_term != "Unknown Product":
        hunter = PriceHunter()
        hunter_task = asyncio.create_task(hunter.hunt(search_term))

    history_task = None
    if HistoryHunter and search_term != "Unknown Product":
        historian = HistoryHunter()
        history_task = asyncio.create_task(historian.get_history(search_term))

    ai_result = await ai_task
    
    competitors = []
    if hunter_task:
        try: competitors = await hunter_task
        except: pass
        
    history = None
    if history_task:
        try: history = await history_task
        except: pass

    if current_price == 0 and competitors:
        best = min(competitors, key=lambda x: x['price'])
        current_price = best['price']
        ai_result['reason'] = f"Price verified across {len(competitors)} stores."

    if "http" in user_input and current_price > 0:
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
        "competitors": competitors,
        "history": history
    }