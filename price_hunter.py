import asyncio
from playwright.async_api import async_playwright
from thefuzz import fuzz

class PriceHunter:
    # --- AGENT 1: FLIPKART ---
    async def search_flipkart(self, page, query):
        try:
            print(f"🕵️‍♂️ Scanning Flipkart for '{query}'...")
            await page.goto(f"https://www.flipkart.com/search?q={query}", timeout=15000)
            print("✅ Flipkart: Page loaded")
            
            try:
                await page.wait_for_selector('div.RG5Slk, div.KzDlHZ, div._4rR01T, a.s1Q9rs', timeout=5000)
                print("✅ Flipkart: Product cards detected")
            except Exception as e:
                print(f"⚠️ Flipkart: No product cards found: {e}")

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
            
            print(f"📊 Flipkart: Found {len(products)} products")

            for idx, item in enumerate(products, 1):
                try:
                    price_clean = int(item['price'].replace("₹", "").replace(",", "").split(" ")[0].strip())
                    match_score = fuzz.partial_ratio(query.lower(), item['title'].lower())
                    print(f"  [{idx}] Match: {match_score}% | {item['title'][:50]}... @ ₹{price_clean}")
                    
                    if match_score > 60:
                        full_link = "https://www.flipkart.com" + item['link'] if item['link'] and not item['link'].startswith("http") else item['link']
                        print(f"✅ Flipkart MATCH: {item['title'][:50]}... @ ₹{price_clean}")
                        return {"site": "Flipkart", "title": item['title'], "price": price_clean, "link": full_link}
                except Exception as e:
                    print(f"  ⚠️ Parse error on item {idx}: {e}")
                    continue 
            
            print("❌ Flipkart: No matches above 60% threshold")
            return None
        except Exception as e:
            print(f"❌ Flipkart Error: {e}")
            return None

    # --- AGENT 2: CROMA (Popup Killer Edition) ---
    async def search_croma(self, page, query):
        try:
            print(f"🕵️‍♂️ Scanning Croma for '{query}'...")
            await page.goto("https://www.croma.com/", timeout=20000)
            
            # 1. POPUP KILLER & WAITER
            try:
                # Wait for page to settle
                await page.wait_for_load_state('domcontentloaded')
                # Press ESCAPE to close "Select Pincode" or "Login" popups
                await page.keyboard.press("Escape")
                await asyncio.sleep(1) 
            except: pass

            # 2. FIND SEARCH BAR (The "Dumb" Strategy)
            # We look for ANY visible text input. The search bar is usually the first one in the header.
            try:
                # Selector: Find any input that is text or search type
                search_input = await page.wait_for_selector('input[type="text"], input[type="search"]', state="visible", timeout=15000)
                
                if search_input:
                    await search_input.click()
                    await search_input.fill(query)
                    await search_input.press("Enter")
                    print("✅ Croma: Search query submitted.")
                else:
                    print("❌ Croma: No search bar found.")
                    return None

                # 3. WAIT FOR RESULTS
                # Increased timeout to 15s because Croma is slow
                await page.wait_for_selector('li.product-item, div.product-item, div.cp-product-box', timeout=15000)
                
            except Exception as e:
                print(f"❌ Croma Navigation Failed: {e}")
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
            # STEALTH MODE - WITH DOCKER/RENDER FLAGS
            browser = await p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-dev-shm-usage']
            )
            context = await browser.new_context(
                # Real User Agent is critical for Croma
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            
            page1 = await context.new_page()
            page2 = await context.new_page()
            
            task1 = self.search_flipkart(page1, clean_query)
            task2 = self.search_croma(page2, clean_query)
            
            res1, res2 = await asyncio.gather(task1, task2, return_exceptions=True)
            await browser.close()
            
            if res1 and not isinstance(res1, Exception): 
                results.append(res1)
            if res2 and not isinstance(res2, Exception): 
                results.append(res2)
            
        return results

if __name__ == "__main__":
    hunter = PriceHunter()
    print(asyncio.run(hunter.hunt("OnePlus 13R")))