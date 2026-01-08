from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)
CORS(app) # This allows your askziva.me frontend to talk to this backend

# --- THE SCRAPER LOGIC (Your Ziva Engine) ---
def ziva_truth_engine(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
        "Accept-Language": "en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7"
    }
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            return {"verdict": "⚠️ BLOCKED", "reason": "Bot detection triggered"}
            
        soup = BeautifulSoup(response.content, "html.parser")
        
        # Title
        title = soup.find("span", {"id": "productTitle"})
        title_text = title.get_text().strip() if title else "Title Not Found"
        
        # Price
        price = soup.find("span", {"class": "a-price-whole"})
        if price:
            price_text = price.get_text().replace(".", "").strip()
        else:
            price_text = "Hidden"
            
        return {
            "verdict": "✅ ONLINE",
            "product": title_text[:100] + "...",
            "price": "₹" + price_text
        }
    except Exception as e:
        return {"verdict": "❌ ERROR", "reason": str(e)}

# --- THE API ROUTE (The Waiter) ---
@app.route('/')
def home():
    return "Ziva Brain is Running! 🧠"

@app.route('/scan', methods=['POST'])
def scan_endpoint():
    data = request.get_json()
    if not data or 'url' not in data:
        return jsonify({"error": "No URL provided"}), 400
        
    url = data['url']
    result = ziva_truth_engine(url)
    return jsonify(result)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
