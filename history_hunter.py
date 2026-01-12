import asyncio
from playwright.async_api import async_playwright
import re

try:
    from playwright_stealth import stealth_async as stealth_fn
except:
    async def stealth_fn(page): pass

class HistoryHunter:
    async def get_history(self, clean_query):
        print(f"📉 History Hunter: Checking '{clean_query}'...")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-dev-shm-usage'])
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = await context.new_page()
            await stealth_fn(page)
            
            try:
                # 1. SEARCH
                await page.goto(f"https://pricehistoryapp.com/search?q={clean_query}", timeout=25000, wait_until="domcontentloaded")
                
                # 2. FIND PRODUCT LINK (More robust selector)
                try:
                    # Click the first meaningful result (usually inside a content div)
                    await page.wait_for_selector('a[href*="/product/"]', timeout=8000)
                    await page.click('a[href*="/product/"]', timeout=5000)
                except:
                    print("❌ History: No product results found.")
                    await browser.close(); return None

                # 3. READ PAGE TEXT
                await page.wait_for_load_state('domcontentloaded')
                page_text = await page.evaluate("document.body.innerText")
                
                # Regex to find "Lowest Price is ₹XX,XXX"
                lowest_match = re.search(r'lowest price.*?₹?([\d,]+)', page_text, re.IGNORECASE)
                average_match = re.search(r'average.*?price.*?₹?([\d,]+)', page_text, re.IGNORECASE)
                
                lowest = int(lowest_match.group(1).replace(",", "")) if lowest_match else 0
                average = int(average_match.group(1).replace(",", "")) if average_match else 0
                
                await browser.close()
                
                if lowest > 0:
                    return {"lowest": lowest, "average": average}
                return None

            except Exception as e:
                print(f"❌ History Error: {e}")
                await browser.close()
                return None