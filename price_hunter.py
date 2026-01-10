import asyncio
from playwright.async_api import async_playwright
from thefuzz import fuzz
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

class PriceHunter:
    # --- AGENT 1: FLIPKART ---
    async def search_flipkart(self, page, query):
        try:
            print(f"🕵️‍♂️ Scanning Flipkart for '{query}'...")
            await page.goto(f"https://www.flipkart.com/search?q={query}", timeout=30000, wait_until="domcontentloaded")
            await asyncio.sleep(3)  # Let JS render
            
            try:
                # More lenient selector - just wait for any product container
                await page.wait_for_selector('div._75nlfW, div._1AtVbE, div.tUxRFH, div[data-id]', timeout=10000)
            except:
                print("⚠️ Flipkart: No product cards detected")
                return None

            products = await page.eval_on_selector_all('div._75nlfW, div._1AtVbE, div.tUxRFH, div[data-id]', """
                elements => elements.map(el => {
                    const titleEl = el.querySelector('div.RG5Slk, div.KzDlHZ, div._4rR01T, a.s1Q9rs');
                    const priceEl = el.querySelector('div.hZ3P6w, div.DeU9vF, div.Nx9bqj, div._30jeq3');
                    const linkEl = el.querySelector('a');
                    if (titleEl && priceEl) {
                        return { title: titleEl.innerText, price: priceEl.innerText, link: linkEl ? linkEl.getAttribute('href') : null };
                    }
                    return null;
                }).filter(item => item !== null)
            """)

            for item in products:
                try:
                    price_clean = int(item['price'].replace("₹", "").replace(",", "").split(" ")[0].strip())
                    if fuzz.partial_ratio(query.lower(), item['title'].lower()) > 50:  # Lower threshold
                        full_link = "https://www.flipkart.com" + item['link'] if item['link'] and not item['link'].startswith("http") else item['link']
                        print(f"✅ Flipkart: {item['title'][:50]} @ ₹{price_clean}")
                        return {"site": "Flipkart", "title": item['title'], "price": price_clean, "link": full_link}
                except: continue 
            print("⚠️ Flipkart: No matching products after fuzzy match")
            return None
        except Exception as e:
            print(f"❌ Flipkart Error: {e}")
            return None

    # --- AGENT 2: CROMA (Robust Edition) ---
    async def search_croma(self, page, query):
        try:
            print(f"🕵️‍♂️ Scanning Croma for '{query}'...")
            await page.goto("https://www.croma.com/", timeout=30000, wait_until="domcontentloaded")
            await asyncio.sleep(2)
            
            # 1. POPUP KILLER
            try:
                await page.keyboard.press("Escape")
                await asyncio.sleep(0.5) 
            except: pass

            # 2. FIND SEARCH BAR - Try multiple strategies
            search_input = None
            selectors = [
                'input[placeholder*="search" i]',  # Case-insensitive search placeholder
                'input[type="search"]',
                'input[name="search"]',
                'input#search',
                'input.search-box',
                'input[type="text"]'
            ]
            
            for selector in selectors:
                try:
                    search_input = await page.wait_for_selector(selector, state="visible", timeout=3000)
                    if search_input:
                        print(f"✅ Croma: Found search using {selector}")
                        break
                except: continue
            
            if not search_input:
                print("❌ Croma: Could not locate search bar with any selector")
                return None

            # 3. SEARCH
            try:
                await search_input.click()
                await search_input.fill(query)
                await search_input.press("Enter")
                await asyncio.sleep(3)  # Wait for results
                
                # Wait for product cards
                await page.wait_for_selector('li.product-item, div.product-item, div.cp-product-box, a[href*="/p/"]', timeout=15000)
            except Exception as e:
                print(f"❌ Croma: Search/Results failed - {e}")
                return None

            # 4. SCRAPE DATA
            data = await page.evaluate("""() => {
                const card = document.querySelector('li.product-item, div.product-item, div.cp-product-box');
                if (!card) return null;
                
                let title = card.querySelector('h3.product-title, h3 a, .product-title a');
                
                let price = card.querySelector('.amount');
                if (!price) price = card.querySelector('.new-price');
                if (!price) price = card.querySelector('.cp-price');

                let link = card.querySelector('a');
                if (title && title.tagName === 'A') link = title;

                return { 
                    title: title ? title.innerText : null, 
                    price: price ? price.innerText : null, 
                    link: link ? link.getAttribute('href') : null 
                };
            }""")

            if data and data['title'] and data['price']:
                raw_price = data['price'].replace("₹", "").replace(",", "").strip()
                price_clean = int(float(raw_price))
                full_link = "https://www.croma.com" + data['link'] if not data['link'].startswith("http") else data['link']
                
                print(f"✅ Found on Croma: {data['title']} @ ₹{price_clean}")
                return {"site": "Croma", "title": data['title'], "price": price_clean, "link": full_link}
            
            print("❌ Croma: Results loaded but scraper couldn't read data.")
            return None
        except Exception as e:
            print(f"❌ Croma Error: {e}")
            return None

    # --- THE MANAGER ---
    async def hunt(self, original_title):
        clean_query = original_title.split("(")[0].split("|")[0].strip()
        results = []
        
        async with async_playwright() as p:
            # Hardened launch for container hosts
            browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"]) 
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 800}
            )
            context.set_default_timeout(25000)
            
            page1 = await context.new_page()
            page2 = await context.new_page()
            await stealth_fn(page1)
            await stealth_fn(page2)
            
            task1 = self.search_flipkart(page1, clean_query)
            task2 = self.search_croma(page2, clean_query)
            
            # Wait for both tasks with exception handling
            res1, res2 = None, None
            try:
                res1, res2 = await asyncio.gather(task1, task2, return_exceptions=True)
                # Filter out exceptions
                if isinstance(res1, Exception):
                    print(f"⚠️ Flipkart task exception: {res1}")
                    res1 = None
                if isinstance(res2, Exception):
                    print(f"⚠️ Croma task exception: {res2}")
                    res2 = None
            except Exception as e:
                print(f"⚠️ Market scanner gather error: {e}")
            
            # Close browser after all tasks complete
            try:
                await browser.close()
            except:
                pass
            
            if res1: results.append(res1)
            if res2: results.append(res2)
            
        return results

if __name__ == "__main__":
    hunter = PriceHunter()
    print(asyncio.run(hunter.hunt("OnePlus 13R")))