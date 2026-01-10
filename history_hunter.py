import asyncio
from playwright.async_api import async_playwright
import re

class HistoryHunter:
    async def get_history(self, query):
        print(f"📉 History Hunter: Checking past prices for '{query}'...")
        # Clean query: "Apple iPhone 14 (Midnight...)" -> "Apple iPhone 14"
        clean_query = query.split("(")[0].split("|")[0].strip()
        
        async with async_playwright() as p:
            # STEALTH MODE: headless=True
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = await context.new_page()
            
            try:
                # 1. SEARCH
                await page.goto(f"https://pricehistoryapp.com/search?q={clean_query}", timeout=20000)
                
                # 2. FIND PRODUCT LINK
                try:
                    await page.wait_for_selector('div', state="attached")
                    # We click the first product card
                    first_product = await page.wait_for_selector('a[href*="/product/"]', timeout=8000)
                    
                    if first_product:
                        product_url = await first_product.get_attribute('href')
                        full_url = f"https://pricehistoryapp.com{product_url}" if not product_url.startswith("http") else product_url
                        print(f"📍 Analyzing History Page: {full_url}")
                        await page.goto(full_url, timeout=20000)
                    else:
                        print("❌ History: No product links found.")
                        await browser.close(); return None
                except:
                    print("❌ History: Search failed.")
                    await browser.close(); return None

                # 3. READ THE SUMMARY SENTENCE
                # We look for the text block containing "lowest price is"
                try:
                    await page.wait_for_selector("text=lowest price is", timeout=10000)
                    
                    # Extract the full description text
                    page_text = await page.evaluate("""() => {
                        // Find the paragraph that talks about price history
                        const elements = document.querySelectorAll('p, div, span');
                        for (let el of elements) {
                            if (el.innerText.includes('lowest price is') && el.innerText.includes('average')) {
                                return el.innerText;
                            }
                        }
                        return document.body.innerText; // Fallback to full page text
                    }""")
                    
                    # 4. REGEX PARSING (The Magic Part)
                    # Pattern: "lowest price is 50999" ... "average and highest price are 70760"
                    
                    lowest_match = re.search(r'lowest price is\s*₹?([\d,]+)', page_text)
                    average_match = re.search(r'average.*?price.*?₹?([\d,]+)', page_text)
                    
                    lowest = 0
                    average = 0
                    
                    if lowest_match:
                        lowest = int(lowest_match.group(1).replace(",", ""))
                    
                    if average_match:
                        average = int(average_match.group(1).replace(",", ""))
                    
                    await browser.close()
                    
                    if lowest > 0:
                        print(f"✅ Corrected History Data: Low: {lowest} | Avg: {average}")
                        return {"lowest": lowest, "average": average}
                    else:
                        print("❌ History: Could not parse numbers from text.")
                        return None

                except Exception as e:
                    print(f"❌ History Text Not Found: {e}")
                    await browser.close()
                    return None

            except Exception as e:
                print(f"❌ History Error: {e}")
                await browser.close()
                return None

# TEST BLOCK
if __name__ == "__main__":
    hunter = HistoryHunter()
    # Test with the exact iPhone example you showed
    print(asyncio.run(hunter.get_history("Apple iPhone 14")))
