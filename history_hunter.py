import asyncio
from playwright.async_api import async_playwright
# Stealth import compatibility
try:
    from playwright_stealth import stealth_async as stealth_fn
except Exception:
    async def stealth_fn(page): pass
import re

class HistoryHunter:
    async def get_history(self, query):
        print(f"📉 History Hunter: Checking '{query}'...")
        clean_query = query.split("(")[0].split("|")[0].strip()
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"]) 
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = await context.new_page()
            await stealth_fn(page)
            
            try:
                # 1. SEARCH
                await page.goto(f"https://pricehistoryapp.com/search?q={clean_query}", timeout=30000, wait_until="domcontentloaded")
                await page.wait_for_timeout(2000)
                
                # 2. GRAB LINK DIRECTLY (Don't Click/Navigate if we can avoid it)
                product_url = await page.evaluate("""() => {
                    const link = document.querySelector('a[href*="/product/"]');
                    return link ? link.getAttribute('href') : null;
                }""")

                if not product_url:
                    print("❌ History: No results found.")
                    await browser.close()
                    return None
                
                # 3. GO TO PRODUCT PAGE
                full_url = f"https://pricehistoryapp.com{product_url}" if not product_url.startswith("http") else product_url
                await page.goto(full_url, timeout=30000, wait_until="domcontentloaded")
                
                # 4. SCRAPE STATS
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