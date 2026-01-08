import os
import google.generativeai as genai
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import re

app = Flask(__name__)
CORS(app)

# 1. SETUP GEMINI (The AI Brain)
# We get the key from Render's secret vault
api_key = os.environ.get("GEMINI_API_KEY")
if api_key:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-pro')
    print("🧠 AI CORTEX: ONLINE")
else:
    print("⚠️ AI CORTEX: OFFLINE (No Key Found)")
    model = None

def ziva_truth_engine(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Accept-Language": "en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7"
    }
    
    try:
        # --- PHASE 1: SCRAPING (The Eyes) ---
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.content, "html.parser")
        
        # Title
        title_tag = soup.find("span", {"id": "productTitle"})
        title_text = title_tag.get_text().strip() if title_tag else "Unknown Product"

        # Price
        price_tag = soup.find("span", {"class": "a-price-whole"})
        price = "₹" + price_tag.get_text().replace(".", "").strip() if price_tag else "Price Hidden"
        
        # Rating & Reviews (The Data)
        rating = 0.0
        review_count = 0
        
        # ... (Same Scraping Logic as before for Stars/Reviews) ...
        rating_tag = soup.find("span", {"class": "a-icon-alt"})
        if rating_tag:
             try: rating = float(rating_tag.get_text().split(" ")[0])
             except: pass
             
        review_selectors = [{"id": "acrCustomerReviewText"}, {"data-hook": "total-review-count"}, {"class": "a-size-base", "dir": "auto"}]
        for selector in review_selectors:
            if review_count > 0: break
            tag = soup.find("span", selector)
            if tag:
                try: review_count = int(re.findall(r'\d+', tag.get_text().replace(",", ""))[0])
                except: pass

        # --- PHASE 2: AI ANALYSIS (The Cortex) ---
        ai_verdict = "NEUTRAL"
        ai_reason = "AI did not run."
        
        if model:
            try:
                # We ask Gemini to judge the product title
                prompt = f"""
                You are a fraud detection AI. Analyze this Amazon product title and price.
                Product: "{title_text}"
                Price: "{price}"
                
                Is this likely a scam, a fake product, or misleading? 
                If it looks like a generic drop-shipped item with random keywords, say SUSPICIOUS.
                If it looks like a legitimate brand product, say SAFE.
                
                Respond in this format: VERDICT | REASON
                Example: SAFE | Trusted Brand Name.
                Example: SUSPICIOUS | Nonsense brand name and impossible specs.
                """
                response = model.generate_content(prompt)
                text = response.text.strip()
                if "|" in text:
                    ai_verdict, ai_reason = text.split("|", 1)
                    ai_verdict = ai_verdict.strip()
                    ai_reason = ai_reason.strip()
            except Exception as e:
                print(f"AI Error: {e}")

        # --- PHASE 3: THE FINAL JUDGMENT (Synthesis) ---
        # We combine Hard Data (Stars) with Soft Data (AI)
        
        final_verdict = "⚠️ UNKNOWN"
        final_reason = "Insufficient Data"
        
        # RULE 1: If AI screams SCAM, we listen.
        if "SUSPICIOUS" in ai_verdict.upper():
            final_verdict = "❌ HIGH RISK (AI ALERT)"
            final_reason = f"AI Detection: {ai_reason}"
            
        # RULE 2: If Data screams SCAM, we listen.
        elif review_count < 10 and review_count >= 0:
            final_verdict = "❌ HIGH RISK"
            final_reason = "New Seller (Less than 10 reviews)."
            
        # RULE 3: If both match, it is Safe.
        elif rating >= 4.0 and review_count > 50:
            final_verdict = "✅ LIKELY SAFE"
            final_reason = f"Verified by AI & Data ({rating} stars)."
            
        return {
            "verdict": final_verdict,
            "reason": final_reason,
            "product": title_text[:60] + "...",
            "price": price
        }

    except Exception as e:
        return {"verdict": "❌ ERROR", "reason": str(e), "product": "Error", "price": "Error"}

@app.route('/')
def home():
    return "Ziva Cortex (Gemini Enabled) is Online! 🧠⚡"

@app.route('/scan', methods=['POST'])
def scan_endpoint():
    data = request.get_json()
    if not data or 'url' not in data:
        return jsonify({"error": "No URL provided"}), 400
    result = ziva_truth_engine(data['url'])
    return jsonify(result)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)