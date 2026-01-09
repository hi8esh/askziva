import os
import google.generativeai as genai
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime  # <--- NEW: Give Ziva a watch

app = Flask(__name__)
CORS(app)

# 1. SETUP GEMINI
api_key = os.environ.get("GEMINI_API_KEY")
if api_key:
    genai.configure(api_key=api_key)
    # Sticking to the model you found works, but adding logic to fix the date issue
    model = genai.GenerativeModel('models/gemini-3-flash-preview') 
    print("🧠 AI CORTEX: ONLINE (Gemini 3 Flash)")
else:
    print("⚠️ AI CORTEX: OFFLINE (No Key Found)")
    model = None

def ziva_truth_engine(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Accept-Language": "en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7"
    }
    
    try:
        # --- PHASE 1: DEEP SCRAPING ---
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.content, "html.parser")
        
        # Title
        title_tag = soup.find("span", {"id": "productTitle"})
        title_text = title_tag.get_text().strip() if title_tag else "Unknown Product"

        # Price
        price_tag = soup.find("span", {"class": "a-price-whole"})
        price = "₹" + price_tag.get_text().replace(".", "").strip() if price_tag else "Price Hidden"
        
        # Details (Bullets)
        features = ""
        feature_bullets = soup.find("div", {"id": "feature-bullets"})
        if feature_bullets:
            features = feature_bullets.get_text().strip()[:500]
        
        # Rating & Reviews
        rating = 0.0
        review_count = 0
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

        # --- PHASE 2: AI ANALYSIS (Time-Aware) ---
        # --- PHASE 2: AI ANALYSIS (Focused Mode) ---
        ai_verdict = "NEUTRAL"
        ai_reason = "AI did not run."
        
        if model:
            try:
                # UPDATED PROMPT: We strictly forbid the AI from guessing release dates.
                prompt = f"""
                Act as Ziva, a fraud detection AI.
                
                Product: "{title_text}"
                Price: "{price}"
                Review Count: {review_count}
                Details: "{features}"
                
                RULES:
                1. TRUST THE REVIEW COUNT: If reviews > 100, the product is REAL and RELEASED. Do not claim it is "unreleased" or "rumored".
                2. IGNORE your training data cutoff regarding release dates.
                3. FOCUS ONLY ON SCAMS: Look for "16TB SSD for $20" or gibberish brand names.
                4. If the specs look realistic for the price, verdict is SAFE.
                
                Respond in this format: VERDICT | REASON
                Example: SAFE | Specs match price and high review count confirms authenticity.
                Example: SUSPICIOUS | Generic brand name with impossible specs.
                """
                response = model.generate_content(prompt)
                text = response.text.strip()
                if "|" in text:
                    ai_verdict, ai_reason = text.split("|", 1)
                    ai_verdict = ai_verdict.strip()
                    ai_reason = ai_reason.strip()
            except Exception as e:
                print(f"AI Error: {e}")
                ai_reason = f"AI Error: {str(e)}"

        # --- PHASE 3: FINAL JUDGMENT ---
        final_verdict = "⚠️ UNKNOWN"
        final_reason = "Insufficient Data"
        
        # Logic Fix: If reviews exist, we override the AI's "Unreleased" hallucination
        if "SUSPICIOUS" in ai_verdict.upper():
            if "unreleased" in ai_reason.lower() and review_count > 500:
                 final_verdict = "✅ LIKELY SAFE"
                 final_reason = f"Released Product: {review_count} verified reviews override AI release date warning."
            else:
                final_verdict = "❌ HIGH RISK (AI ALERT)"
                final_reason = f"Ziva Intelligence: {ai_reason}"
                
        elif review_count < 10 and review_count >= 0:
            final_verdict = "❌ HIGH RISK"
            final_reason = "New Seller (Less than 10 reviews)."
        elif rating >= 4.0 and review_count > 50:
            final_verdict = "✅ LIKELY SAFE"
            final_reason = f"Verified: {rating} stars & AI Analysis."
            
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
    return "Ziva Cortex (Time-Aware) is Online! 🧠🕰️"

@app.route('/scan', methods=['POST'])
def scan_endpoint():
    data = request.get_json()
    if not data or 'url' not in data:
        return jsonify({"error": "No URL provided"}), 400
    result = ziva_truth_engine(data['url'])
    return jsonify(result)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
