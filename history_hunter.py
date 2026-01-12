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
            page = await browser.new_page()
            await stealth_fn(page)
            
            # BLOCK ASSETS
            await page.route("**/*", lambda route: route.abort() 
                if route.request.resource_type in ["image", "media", "font"] 
                else route.continue_())
            
            try:
                await page.goto(f"https://pricehistoryapp.com/search?q={clean_query}", timeout=25000, wait_until="commit")
                try: await page.wait_for_selector('a[href*="/product/"]', timeout=5000) 
                except: pass
                
                # Try finding link
                try: await page.click('a[href*="/product/"]', timeout=3000)
                except: 
                    print("❌ History: No product results found.")
                    await browser.close(); return None

                # Read stats
                try: await page.wait_for_selector('body', timeout=5000)
                except: pass
                
                page_text = await page.evaluate("document.body.innerText")
                lowest_match = re.search(r'lowest price.*?₹?([\d,]+)', page_text, re.IGNORECASE)
                average_match = re.search(r'average.*?price.*?₹?([\d,]+)', page_text, re.IGNORECASE)
                
                lowest = int(lowest_match.group(1).replace(",", "")) if lowest_match else 0
                average = int(average_match.group(1).replace(",", "")) if average_match else 0
                
                await browser.close()
                if lowest > 0: return {"lowest": lowest, "average": average}
                return None

            except Exception as e:
                print(f"❌ History Error: {e}")
                await browser.close()
                return None