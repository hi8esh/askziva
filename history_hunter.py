import asyncio
from playwright.async_api import async_playwright
# Stealth import compatibility: normalize to a callable function
try:
    from playwright_stealth import stealth_async as stealth_fn  # v1 API
except Exception:
    try:
        from playwright_stealth import stealth as stealth_fn  # v2 API may export a function or a module
        if not callable(stealth_fn):
            import playwright_stealth as _ps
            if hasattr(_ps, "stealth_async") and callable(getattr(_ps, "stealth_async")):
                async def stealth_fn(page):
                    return await _ps.stealth_async(page)
            elif hasattr(_ps, "stealth") and callable(getattr(_ps, "stealth")):
                async def stealth_fn(page):
                    return await _ps.stealth(page)
            else:
                async def stealth_fn(page):
                    return
    except Exception:
        async def stealth_fn(page):
            return
import re

class HistoryHunter:
    async def get_history(self, query):
        print(f"📉 History Hunter: Checking past prices for '{query}'...")
        # Clean query: "Apple iPhone 14 (Midnight...)" -> "Apple iPhone 14"
        clean_query = query.split("(")[0].split("|")[0].strip()
        
        async with async_playwright() as p:
            # Hardened launch for container hosts
            browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"]) 
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = await context.new_page()
            await stealth_fn(page)
            
            try:
                # 1. SEARCH
                await page.goto(f"https://pricehistoryapp.com/search?q={clean_query}", timeout=30000, wait_until="domcontentloaded")
                
                # 2. FIND PRODUCT LINK
                try:
                    # We click the first product card
                    await page.click('a[href*="/product/"]', timeout=8000)
                except:
                    print("❌ History: Product not found.")
                    await browser.close()
                    return None

                await page.wait_for_load_state('domcontentloaded')
                
                # 3. SCRAPE STATS
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