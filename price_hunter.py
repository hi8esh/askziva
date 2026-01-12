import asyncio
from playwright.async_api import async_playwright
from thefuzz import fuzz

try:
    from playwright_stealth import stealth_async as stealth_fn
except:
    async def stealth_fn(page): pass

class PriceHunter:
    async def search_flipkart(self, page, query):
        try:
            print(f"🕵️‍♂️ Scanning Flipkart for '{query}'...")
            await page.goto(f"https://www.flipkart.com/search?q={query}", timeout=20000, wait_until="domcontentloaded")
            await page.wait_for_timeout(1000)

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
                    if fuzz.partial_ratio(query.lower(), item['title'].lower()) > 50:
                        full_link = "https://www.flipkart.com" + item['link'] if item['link'] and not item['link'].startswith("http") else item['link']
                        return {"site": "Flipkart", "title": item['title'], "price": price_clean, "link": full_link}
                except: continue 
            return None
        except: return None

    async def search_croma(self, page, query):
        try:
            print(f"🕵️‍♂️ Scanning Croma for '{query}'...")
            await page.goto(f"https://www.croma.com/searchB?q={query}%20", timeout=25000, wait_until="domcontentloaded")
            
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
                
                if fuzz.partial_ratio(query.lower(), data['title'].lower()) > 40:
                    return {"site": "Croma", "title": data['title'], "price": price_clean, "link": full_link}
            return None
        except: return None

    async def search_amazon(self, page, query):
        try:
            print(f"🕵️‍♂️ Scanning Amazon for '{query}'...")
            await page.goto(f"https://www.amazon.in/s?k={query}", timeout=20000, wait_until="domcontentloaded")
            await page.wait_for_timeout(1500)

            data = await page.evaluate("""() => {
                const card = document.querySelector('div[data-component-type="s-search-result"]');
                if (!card) return null;
                const title = card.querySelector('h2 a span')?.innerText;
                const price = card.querySelector('.a-price-whole')?.innerText;
                const link = card.querySelector('h2 a')?.getAttribute('href');
                return { title, price, link };
            }""")

            if data and data['title'] and data['price']:
                price_clean = int(data['price'].replace(",", "").replace(".", "").strip())
                full_link = "https://www.amazon.in" + data['link'] if not data['link'].startswith("http") else data['link']
                return {"site": "Amazon", "title": data['title'], "price": price_clean, "link": full_link}
            return None
        except: return None

    async def hunt(self, clean_query):
        results = []
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-dev-shm-usage'])
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            
            # Create pages
            pages = [await context.new_page() for _ in range(3)]
            for pg in pages: await stealth_fn(pg)
            
            # Run tasks in parallel
            tasks = [
                self.search_flipkart(pages[0], clean_query),
                self.search_croma(pages[1], clean_query),
                self.search_amazon(pages[2], clean_query) 
            ]
            
            res_list = await asyncio.gather(*tasks)
            await browser.close()
            
            for res in res_list:
                if res: results.append(res)
            
        return results