async function scanLink() {
    var link = document.getElementById("userInput").value;
    var resultBox = document.getElementById("result-box");
    var button = document.querySelector("button");

    if (link === "") {
        alert("Please paste a link or product name first!");
        return;
    }

    // UI: Show Loading State
    resultBox.style.display = "block";
    resultBox.className = ""; 
    resultBox.innerHTML = "📡 <strong>SCANNING:</strong> Ziva is analyzing market data...<br><em>(Checking Amazon, Flipkart, Croma & History)</em>";
    button.disabled = true;
    button.innerText = "Scanning...";

    try {
        const response = await fetch('https://ziva-brain.onrender.com/scan', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url: link })
        });

        const data = await response.json();

        button.disabled = false;
        button.innerText = "Ask Ziva";

        // UI Colors
        let color = "#3fb950"; // Green
        if (data.verdict.includes("SUSPICIOUS")) color = "#d29922"; // Yellow
        if (data.verdict.includes("HIGH RISK")) color = "#f85149"; // Red
        const icon = (data.verdict.includes("SAFE")) ? "✅" : "⚠️";

        // History Section
        let historyHtml = "";
        if (data.history && data.history.lowest) {
            historyHtml = `
            <div style="margin-top: 10px; padding-top: 10px; border-top: 1px dashed #ccc;">
                <div style="font-size: 11px; color: #666; margin-bottom: 5px;">📉 PRICE HISTORY</div>
                <div style="display: flex; justify-content: space-between;">
                    <span>Lowest Ever:</span>
                    <span style="font-weight: bold; color: #3fb950;">₹${data.history.lowest.toLocaleString()}</span>
                </div>
                <div style="display: flex; justify-content: space-between;">
                    <span>Average:</span>
                    <span>₹${data.history.average.toLocaleString()}</span>
                </div>
            </div>`;
        }

        // Market Section
        let marketHtml = "";
        if (data.competitors && data.competitors.length > 0) {
            marketHtml = `<div style="margin-top: 10px; padding-top: 10px; border-top: 1px dashed #ccc;">
                <div style="font-size: 11px; color: #666; margin-bottom: 5px;">💰 COMPETITORS</div>`;
            
            data.competitors.forEach(comp => {
                let priceStyle = "font-weight: bold;";
                // Highlight if cheaper than current found price
                if (data.current_price > 0 && comp.price < data.current_price) {
                    priceStyle += " color: #d29922; text-decoration: underline;";
                }

                marketHtml += `
                <div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
                    <span>${comp.site}</span>
                    <div>
                        <span style="${priceStyle}">₹${comp.price.toLocaleString()}</span>
                        <a href="${comp.link}" target="_blank" style="margin-left: 5px;">↗</a>
                    </div>
                </div>`;
            });
            marketHtml += `</div>`;
        }

        // Final HTML
        resultBox.className = (data.verdict.includes("SAFE")) ? "safe" : "scam";
        resultBox.innerHTML = `
            <div style="border-left: 4px solid ${color}; padding-left: 10px;">
                <h3 style="margin: 0; color: ${color};">${icon} ${data.verdict}</h3>
                <p style="margin: 5px 0 0 0; font-size: 0.9em;">${data.product}</p>
                <p style="margin: 5px 0 0 0; font-size: 0.8em; opacity: 0.8;">${data.reason}</p>
            </div>
            ${historyHtml}
            ${marketHtml}
        `;

    } catch (error) {
        console.error("Error:", error);
        resultBox.className = "scam";
        resultBox.innerHTML = "<strong>❌ SERVER ERROR</strong><br>The Ziva Brain is offline or timed out.<br>Try again in 30 seconds.";
        button.disabled = false;
        button.innerText = "Ask Ziva";
    }
}