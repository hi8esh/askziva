import asyncio
from playwright.async_api import async_playwright
import re

class HistoryHunter:
    async def get_history(self, query):
        print(f"📉 History: Checking '{query}'...")
        clean_query = query.split("(")[0].split("|")[0].strip()
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu']
            )
            page = await browser.new_page()
            
            # BLOCK IMAGES
            await page.route("**/*", lambda route: route.abort() 
                if route.request.resource_type in ["image", "media", "font"] 
                else route.continue_())

            try:
                await page.goto(f"https://pricehistoryapp.com/search?q={clean_query}", timeout=25000, wait_until="domcontentloaded")
                
                # Click first result
                try:
                    await page.click('a[href*="/product/"]', timeout=5000)
                except:
                    await browser.close()
                    return None

                await page.wait_for_load_state('domcontentloaded')
                text_content = await page.evaluate("document.body.innerText")
                
                lowest = re.search(r'Lowest Price.*?₹([\d,]+)', text_content, re.IGNORECASE)
                average = re.search(r'Average Price.*?₹([\d,]+)', text_content, re.IGNORECASE)
                
                l_price = int(lowest.group(1).replace(",", "")) if lowest else 0
                a_price = int(average.group(1).replace(",", "")) if average else 0
                
                await browser.close()
                return {"lowest": l_price, "average": a_price}

            except Exception as e:
                print(f"❌ History Error: {e}")
                await browser.close()
                return None