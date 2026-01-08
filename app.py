from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import re

app = Flask(__name__)
CORS(app)

def ziva_truth_engine(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Accept-Language": "en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7"
    }
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            return {"verdict": "⚠️ BLOCKED", "reason": "Bot detection triggered", "product": "Unknown", "price": "Unknown"}

        soup = BeautifulSoup(response.content, "html.parser")
        
        # 1. GET TITLE (Added back)
        title_tag = soup.find("span", {"id": "productTitle"})
        title_text = title_tag.get_text().strip()[:60] + "..." if title_tag else "Product Title Not Found"

        # 2. GET PRICE
        price_tag = soup.find("span", {"class": "a-price-whole"})
        price = "₹" + price_tag.get_text().replace(".", "").strip() if price_tag else "Price Hidden"
        
        # 3. GET RATING
        rating = 0.0
        rating_tag = soup.find("span", {"class": "a-icon-alt"})
        if rating_tag:
            try:
                rating_text = rating_tag.get_text().split(" ")[0]
                rating = float(rating_text)
            except: pass

        # 4. GET REVIEW COUNT (Multi-Selector)
        review_count = 0
        review_selectors = [
            {"id": "acrCustomerReviewText"},
            {"data-hook": "total-review-count"},
            {"class": "a-size-base", "dir": "auto"}
        ]
        for selector in review_selectors:
            if review_count > 0: break
            found_tag = soup.find("span", selector)
            if found_tag:
                try:
                    clean_text = found_tag.get_text().strip().replace(",", "")
                    numbers = re.findall(r'\d+', clean_text)
                    if numbers: review_count = int(numbers[0])
                except: pass

        # 5. THE VERDICT LOGIC
        verdict = "⚠️ UNKNOWN"
        reason = "Insufficient data."
        
        if rating > 0 and review_count == 0:
            verdict = "✅ LIKELY SAFE"
            reason = f"Rating is good ({rating} stars), but review count is hidden."
        elif review_count < 10 and review_count >= 0:
            verdict = "❌ HIGH RISK"
            reason = "Very few reviews (<10). Possible new scam seller."
        elif rating < 3.5:
            verdict = "⚠️ CAUTION"
            reason = f"Low quality rating ({rating} stars). Customers are unhappy."
        elif rating >= 4.0 and review_count > 100:
            verdict = "✅ LIKELY SAFE"
            reason = f"Trusted: {rating} stars from {review_count:,} users."
            
        return {
            "verdict": verdict,
            "reason": reason,
            "product": title_text,
            "price": price
        }

    except Exception as e:
        return {"verdict": "❌ ERROR", "reason": str(e), "product": "Error", "price": "Error"}

# --- API ROUTES ---
@app.route('/')
def home():
    return "Ziva Brain v2.1 is Active! 🧠"

@app.route('/scan', methods=['POST'])
def scan_endpoint():
    data = request.get_json()
    if not data or 'url' not in data:
        return jsonify({"error": "No URL provided"}), 400
    
    # Run the engine
    result = ziva_truth_engine(data['url'])
    return jsonify(result)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
