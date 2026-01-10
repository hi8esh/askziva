async function scanLink() {
    var link = document.getElementById("userInput").value;
    var resultBox = document.getElementById("result-box");
    var button = document.querySelector("button");

    if (link === "") {
        alert("Please paste a link first!");
        return;
    }

    // UI: Show Loading State
    resultBox.style.display = "block";
    resultBox.className = ""; 
    resultBox.innerHTML = "📡 <strong>CONNECTING:</strong> Sending link to Ziva Cloud Engine...<br><em>(This might take 10 seconds while we wake up the server)</em>";
    button.disabled = true;
    button.innerText = "Scanning...";

    try {
        // THE API CALL (Talking to Render)
        const response = await fetch('https://ziva-brain.onrender.com/scan', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ url: link })
        });

        const data = await response.json();

        // Handle the Result
        button.disabled = false;
        button.innerText = "Check Trust";

        // Determine color based on verdict
        let color = "#3fb950"; // Green for SAFE
        if (data.verdict && data.verdict.includes("SUSPICIOUS")) color = "#d29922"; // Orange
        if (data.verdict && data.verdict.includes("HIGH RISK")) color = "#f85149"; // Red
        const icon = (data.verdict && data.verdict.includes("SAFE")) ? "✅" : "⚠️";

        // Get current price from backend
        const currentPrice = data.current_price || 0;

        // --- BUILD RESPONSE WITH HISTORY AND MARKET DATA ---
        let historyHtml = "";
        if (data.history && data.history.lowest) {
            let lowest = data.history.lowest;
            let label = "Lowest Ever:";
            let priceColor = "#3fb950";

            // REAL-TIME CHECK: Is current price lower than history?
            if (currentPrice > 0 && currentPrice < lowest) {
                lowest = currentPrice; // Overwrite history with current reality
                label = "🔥 NEW RECORD LOW:";
                priceColor = "#ffeb3b"; // Bright Yellow/Gold for Record
            }

            historyHtml = `
            <div style="margin-top: 8px; padding-top: 8px; border-top: 1px dashed #ccc;">
                <div style="font-size: 11px; color: #666; margin-bottom: 4px;"><strong>📉 PRICE HISTORY</strong></div>
                <div style="display: flex; justify-content: space-between; font-size: 12px; color: #333;">
                    <span>${label}</span>
                    <span style="color: ${priceColor}; font-weight: bold;">₹${lowest.toLocaleString()}</span>
                </div>
                <div style="display: flex; justify-content: space-between; font-size: 12px; color: #333;">
                    <span>Average:</span>
                    <span>₹${data.history.average.toLocaleString()}</span>
                </div>
            </div>`;
        }

        let marketHtml = "";
        if (data.competitors && data.competitors.length > 0) {
            marketHtml = `<div style="margin-top: 10px; padding-top: 8px; border-top: 1px dashed #ccc;">
                <div style="font-size: 11px; color: #666; margin-bottom: 4px;"><strong>💰 MARKET SCANNER</strong></div>`;
            data.competitors.forEach(comp => {
                // Check if competitor is cheaper than current price
                let dealStyle = "color: #28a745;";  // Readable green
                if (currentPrice > 0 && comp.price < currentPrice) {
                    dealStyle = "color: #ffc107; font-weight: bold; text-decoration: underline;"; // Gold for better deals
                }

                marketHtml += `
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; font-size: 12px;">
                    <span style="color: #333;">${comp.site}</span>
                    <div>
                        <span style="${dealStyle}">₹${comp.price.toLocaleString()}</span>
                        <a href="${comp.link}" target="_blank" style="margin-left: 5px; text-decoration: none; color: #0066cc;">↗</a>
                    </div>
                </div>`;
            });
            marketHtml += `</div>`;
        }

        resultBox.className = (data.verdict && data.verdict.includes("SAFE")) ? "safe" : "scam";
        resultBox.innerHTML = `
            <div style="border-left: 3px solid ${color}; padding-left: 10px;">
                <h3 style="margin: 0; color: ${color}; font-size: 14px;">${icon} ${data.verdict}</h3>
                <p style="margin-top: 5px; font-size: 12px; color: #555; line-height: 1.4;">${data.reason}</p>
            </div>
            ${historyHtml} 
            ${marketHtml}
        `;

    } catch (error) {
        console.error("Error:", error);
        resultBox.className = "scam";
        resultBox.innerHTML = "<strong>❌ SYSTEM ERROR</strong><br>Could not reach the Ziva Cloud Server.<br>It might be sleeping (Free Tier). Try again in 30 seconds.";
        button.disabled = false;
        button.innerText = "Check Trust";
    }
}
