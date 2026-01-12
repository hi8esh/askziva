import asyncio
import random
from playwright.async_api import async_playwright
from thefuzz import fuzz

try:
    from playwright_stealth import stealth_async as stealth_fn
except:
    async def stealth_fn(page): pass

class PriceHunter:
    
    # --- RANDOM AGENTS TO AVOID BLOCKING ---
    def get_user_agent(self):
        agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
        ]
        return random.choice(agents)

    async def search_flipkart(self, page, query):
        try:
            print(f"🕵️‍♂️ Scanning Flipkart for '{query}'...")
            await page.goto(f"https://www.flipkart.com/search?q={query}", timeout=25000, wait_until="domcontentloaded")
            await page.wait_for_timeout(1000)

            # NEW 2025/26 SELECTORS + OLD FALLBACKS
            products = await page.eval_on_selector_all('div.cPHDOP, div._75nlfW, div._1AtVbE', """
                elements => elements.map(el => {
                    // Try multiple title classes
                    const titleEl = el.querySelector('div.KzDlHZ') || 
                                    el.querySelector('a.s1Q9rs') || 
                                    el.querySelector('div._4rR01T');
                                    
                    // Try multiple price classes
                    const priceEl = el.querySelector('div.Nx9bqj') || 
                                    el.querySelector('div._30jeq3');
                                    
                    const linkEl = el.querySelector('a');
                    
                    if (titleEl && priceEl) {
                        return { 
                            title: titleEl.innerText, 
                            price: priceEl.innerText, 
                            link: linkEl ? linkEl.getAttribute('href') : null 
                        };
                    }
                    return null;
                }).filter(item => item !== null)
            """)

            best_match = None
            
            # Scan Top 5 Results
            for item in products[:5]:
                try:
                    price_clean = int(item['price'].replace("₹", "").replace(",", "").split(" ")[0].strip())
                    
                    # Fuzzy Logic: Must be > 40% similar to query
                    ratio = fuzz.partial_ratio(query.lower(), item['title'].lower())
                    print(f"   Flipkart Candidate: {item['title']} | Score: {ratio}")
                    
                    if ratio > 40:
                        full_link = "https://www.flipkart.com" + item['link'] if item['link'] and not item['link'].startswith("http") else item['link']
                        
                        # Logic: Prefer cheaper valid price, or higher match score
                        if best_match is None or (ratio > best_match['score']):
                            best_match = {
                                "site": "Flipkart", 
                                "title": item['title'], 
                                "price": price_clean, 
                                "link": full_link,
                                "score": ratio
                            }
                except: continue 
            
            if best_match: return best_match
            return None
        except Exception as e:
            print(f"❌ Flipkart Error: {e}")
            return None

    async def search_croma(self, page, query):
        try:
            print(f"🕵️‍♂️ Scanning Croma for '{query}'...")
            await page.goto(f"https://www.croma.com/searchB?q={query}%20", timeout=25000, wait_until="domcontentloaded")
            
            data = await page.evaluate("""() => {
                const cards = document.querySelectorAll('li.product-item, div.product-item');
                const items = [];
                
                cards.forEach(card => {
                    const title = card.querySelector('h3.product-title, h3 a')?.innerText;
                    const price = card.querySelector('.amount, .new-price')?.innerText;
                    const link = card.querySelector('h3 a')?.getAttribute('href');
                    if(title && price) items.push({title, price, link});
                });
                return items.slice(0, 3);
            }""")

            for item in data:
                raw_price = item['price'].replace("₹", "").replace(",", "").strip()
                price_clean = int(float(raw_price))
                full_link = "https://www.croma.com" + item['link'] if not item['link'].startswith("http") else item['link']
                
                if fuzz.partial_ratio(query.lower(), item['title'].lower()) > 40:
                    return {"site": "Croma", "title": item['title'], "price": price_clean, "link": full_link}
            return None
        except: return None

    async def search_amazon(self, page, query):
        try:
            print(f"🕵️‍♂️ Scanning Amazon for '{query}'...")
            await page.goto(f"https://www.amazon.in/s?k={query}", timeout=25000, wait_until="domcontentloaded")
            await page.wait_for_timeout(1000)

            results = await page.evaluate("""() => {
                const items = [];
                const cards = document.querySelectorAll('div[data-component-type="s-search-result"]');
                
                cards.forEach(card => {
                    const titleEl = card.querySelector('h2 a span');
                    const priceEl = card.querySelector('.a-price-whole');
                    const linkEl = card.querySelector('h2 a');
                    
                    if (titleEl && priceEl) {
                        items.push({
                            title: titleEl.innerText,
                            price: priceEl.innerText,
                            link: linkEl.getAttribute('href')
                        });
                    }
                });
                return items.slice(0, 5); // Return top 5
            }""")

            best_match = None
            
            for item in results:
                try:
                    price_clean = int(item['price'].replace(",", "").replace(".", "").strip())
                    ratio = fuzz.partial_ratio(query.lower(), item['title'].lower())
                    print(f"   Amazon Candidate: {item['title']} | Score: {ratio}")

                    if ratio > 40:
                        full_link = "https://www.amazon.in" + item['link'] if not item['link'].startswith("http") else item['link']
                        
                        # Pick the first good match (Amazon ranks by relevance usually)
                        return {"site": "Amazon", "title": item['title'], "price": price_clean, "link": full_link}
                except: continue

            return None
        except Exception as e:
            print(f"❌ Amazon Error: {e}")
            return None

    async def hunt(self, clean_query):
        results = []
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-dev-shm-usage'])
            
            # Create isolated contexts with different User Agents
            context1 = await browser.new_context(user_agent=self.get_user_agent())
            context2 = await browser.new_context(user_agent=self.get_user_agent())
            context3 = await browser.new_context(user_agent=self.get_user_agent())
            
            page1 = await context1.new_page()
            page2 = await context2.new_page()
            page3 = await context3.new_page()
            
            await stealth_fn(page1)
            await stealth_fn(page2)
            await stealth_fn(page3)
            
            # Run tasks
            task1 = self.search_flipkart(page1, clean_query)
            task2 = self.search_croma(page2, clean_query)
            task3 = self.search_amazon(page3, clean_query)
            
            # Allow failures without crashing everything
            res_list = await asyncio.gather(task1, task2, task3, return_exceptions=True)
            await browser.close()
            
            for res in res_list:
                if isinstance(res, dict) and res: 
                    results.append(res)
            
        return results