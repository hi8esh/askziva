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
            await page.goto(f"https://www.flipkart.com/search?q={query}", timeout=20000, wait_until="domcontentloaded")
            
            try:
                await page.wait_for_selector('div.RG5Slk, div.KzDlHZ, div._4rR01T, a.s1Q9rs', timeout=5000)
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
        except: return None

    # --- AGENT 2: CROMA ---
    async def search_croma(self, page, query):
        try:
            print(f"🕵️‍♂️ Scanning Croma for '{query}'...")
            await page.goto(f"https://www.croma.com/searchB?q={query}%20", timeout=20000, wait_until="domcontentloaded")
            
            # Popup Killer
            try:
                await page.keyboard.press("Escape")
            except: pass

            try:
                await page.wait_for_selector('li.product-item, div.product-item', timeout=10000)
            except: return None

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
        except: return None

    # --- THE MANAGER ---
    async def hunt(self, original_title):
        clean_query = original_title.split("(")[0].split("|")[0].strip()
        results = []
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-dev-shm-usage'])
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            
            page1 = await context.new_page()
            page2 = await context.new_page()
            await stealth_fn(page1)
            await stealth_fn(page2)
            
            task1 = self.search_flipkart(page1, clean_query)
            task2 = self.search_croma(page2, clean_query)
            
            res1, res2 = await asyncio.gather(task1, task2)
            await browser.close()
            
            if res1: results.append(res1)
            if res2: results.append(res2)
            
        return results