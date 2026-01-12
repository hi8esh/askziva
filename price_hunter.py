import asyncio
from playwright.async_api import async_playwright
from thefuzz import fuzz
# Stealth import compatibility
try:
    from playwright_stealth import stealth_async as stealth_fn
except Exception:
    async def stealth_fn(page): pass

class PriceHunter:
    # --- AGENT 1: FLIPKART ---
    async def search_flipkart(self, page, query):
        try:
            print(f"🕵️‍♂️ Scanning Flipkart for '{query}'...")
            await page.goto(f"https://www.flipkart.com/search?q={query}", timeout=45000, wait_until="domcontentloaded")
            await page.wait_for_timeout(2000) # Just wait 2s, don't look for selectors

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
            return None

    # --- AGENT 2: CROMA ---
    async def search_croma(self, page, query):
        try:
            print(f"🕵️‍♂️ Scanning Croma for '{query}'...")
            await page.goto(f"https://www.croma.com/searchB?q={query}%20", timeout=45000, wait_until="domcontentloaded")
            await page.wait_for_timeout(3000) # Croma is slow, give it 3s

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
        except Exception:
            return None

    # --- AGENT 3: AMAZON ---
    async def search_amazon(self, page, query):
        try:
            print(f"🕵️‍♂️ Scanning Amazon for '{query}'...")
            await page.goto(f"https://www.amazon.in/s?k={query}", timeout=45000, wait_until="domcontentloaded")
            await page.wait_for_timeout(2000) # Force wait

            data = await page.evaluate("""() => {
                // Grab ANY result item
                const results = document.querySelectorAll('div[data-component-type="s-search-result"]');
                for(let card of results) {
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
                }
                return null;
            }""")

            if data:
                price_clean = int(data['price'].replace(",", "").replace(".", "").strip())
                full_link = "https://www.amazon.in" + data['link'] if not data['link'].startswith("http") else data['link']
                return {"site": "Amazon", "title": data['title'], "price": price_clean, "link": full_link}
            return None
        except Exception as e:
            return None

    # --- THE MANAGER ---
    async def hunt(self, original_title):
        clean_query = original_title.split("(")[0].split("|")[0].strip()
        results = []
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"]) 
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            
            # Create pages
            pages = [await context.new_page() for _ in range(3)]
            
            # Stealth
            for page in pages: await stealth_fn(page)
            
            # Run Safe
            tasks = [
                self.search_flipkart(pages[0], clean_query),
                self.search_croma(pages[1], clean_query),
                self.search_amazon(pages[2], clean_query)
            ]
            
            # return_exceptions=True prevents one crash from stopping others
            fetched_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            await browser.close()
            
            for res in fetched_results:
                if isinstance(res, dict): # Check if it's valid data, not an Error
                    results.append(res)
            
        return results