import asyncio
from playwright.async_api import async_playwright
from thefuzz import fuzz

class PriceHunter:
    # --- HELPER: SPEED BOOSTER ---
    async def _optimize_page(self, route):
        """Blocks heavy resources to speed up page load by 10x."""
        if route.request.resource_type in ["image", "stylesheet", "font", "media", "script"]:
            await route.abort()
        else:
            await route.continue_()

    # --- AGENT 1: FLIPKART ---
    async def search_flipkart(self, page, query):
        try:
            # Block junk to load fast
            await page.route("**/*", self._optimize_page)
            
            print(f"🕵️‍♂️ Scanning Flipkart for '{query}'...")
            # Wait only for HTML (domcontentloaded), NOT full page
            await page.goto(f"https://www.flipkart.com/search?q={query}", timeout=25000, wait_until="domcontentloaded")
            
            # Wait for any item to appear
            try:
                await page.wait_for_selector('div._1AtVbE', timeout=5000)
            except: pass

            products = await page.eval_on_selector_all('div[data-id], div._1AtVbE', """
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
                    if fuzz.partial_ratio(query.lower(), item['title'].lower()) > 60:
                        full_link = "https://www.flipkart.com" + item['link'] if item['link'] and not item['link'].startswith("http") else item['link']
                        return {"site": "Flipkart", "title": item['title'], "price": price_clean, "link": full_link}
                except: continue 
            return None
        except Exception as e:
            print(f"❌ Flipkart Error: {e}")
            return None

    # --- AGENT 2: CROMA ---
    async def search_croma(self, page, query):
        try:
            await page.route("**/*", self._optimize_page)
            print(f"🕵️‍♂️ Scanning Croma for '{query}'...")
            
            await page.goto(f"https://www.croma.com/searchB?q={query}%20", timeout=25000, wait_until="domcontentloaded")
            
            try:
                # Croma is weird, sometimes needs a small wait
                await page.wait_for_selector('li.product-item, div.product-item', timeout=5000)
            except: 
                return None

            data = await page.evaluate("""() => {
                const card = document.querySelector('li.product-item, div.product-item');
                if (!card) return null;
                const title = card.querySelector('h3.product-title, h3 a')?.innerText;
                const price = card.querySelector('.amount, .new-price')?.innerText;
                const link = card.querySelector('h3 a')?.getAttribute('href');
                return { title, price, link };
            }""")

            if data and data['title'] and data['price']:
                raw_price = data['price'].replace("₹", "").replace(",", "").strip()
                price_clean = int(float(raw_price))
                full_link = "https://www.croma.com" + data['link'] if not data['link'].startswith("http") else data['link']
                
                if fuzz.partial_ratio(query.lower(), data['title'].lower()) > 50:
                    return {"site": "Croma", "title": data['title'], "price": price_clean, "link": full_link}
            return None
        except Exception as e:
            print(f"❌ Croma Error: {e}")
            return None

    # --- AGENT 3: AMAZON (Scanner Mode) ---
    async def search_amazon(self, page, query):
        try:
            await page.route("**/*", self._optimize_page)
            print(f"🕵️‍♂️ Scanning Amazon for '{query}'...")
            
            await page.goto(f"https://www.amazon.in/s?k={query}", timeout=25000, wait_until="domcontentloaded")
            
            try:
                await page.wait_for_selector('div.s-result-item[data-component-type="s-search-result"]', timeout=5000)
            except: return None

            data = await page.evaluate("""() => {
                const card = document.querySelector('div.s-result-item[data-component-type="s-search-result"]');
                if (!card) return null;
                const titleEl = card.querySelector('h2 a span');
                const priceEl = card.querySelector('.a-price-whole');
                const linkEl = card.querySelector('h2 a');
                
                if (titleEl && priceEl) {
                    return {
                        title: titleEl.innerText,
                        price: priceEl.innerText,
                        link: linkEl.getAttribute('href')
                    };
                }
                return null;
            }""")

            if data:
                price_clean = int(data['price'].replace(",", "").replace(".", "").strip())
                full_link = "https://www.amazon.in" + data['link'] if not data['link'].startswith("http") else data['link']
                return {"site": "Amazon", "title": data['title'], "price": price_clean, "link": full_link}
            return None
        except Exception as e:
            print(f"❌ Amazon Error: {e}")
            return None

    # --- THE MANAGER ---
    async def hunt(self, original_title):
        clean_query = original_title.split("(")[0].split("|")[0].strip()
        results = []
        
        async with async_playwright() as p:
            # Minimal Launch Args for Render
            browser = await p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu']
            )
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            
            page1 = await context.new_page()
            page2 = await context.new_page()
            page3 = await context.new_page()
            
            # Parallel Execution
            t1 = self.search_flipkart(page1, clean_query)
            t2 = self.search_croma(page2, clean_query)
            t3 = self.search_amazon(page3, clean_query)
            
            fetched_results = await asyncio.gather(t1, t2, t3)
            
            await browser.close()
            
            for res in fetched_results:
                if res: results.append(res)
            
        return results