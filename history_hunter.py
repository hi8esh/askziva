import asyncio
from playwright.async_api import async_playwright
import re

class HistoryHunter:
    async def get_history(self, query):
        print(f"📉 History: Checking '{query}'...")
        clean_query = query.split("(")[0].strip()
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-dev-shm-usage']
            )
            page = await browser.new_page()
            
            try:
                await page.goto(f"https://pricehistoryapp.com/search?q={clean_query}", timeout=25000)
                
                # Click first result
                try:
                    await page.click('a[href*="/product/"]', timeout=8000)
                except:
                    print("❌ History: Product not found")
                    await browser.close()
                    return None

                # Wait for text
                await page.wait_for_load_state('domcontentloaded')
                
                # Extract text
                text_content = await page.evaluate("document.body.innerText")
                
                # Regex search for prices
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