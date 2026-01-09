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

        if (data.verdict.includes("SAFE")) {
            resultBox.className = "safe";
            resultBox.innerHTML = `
                <strong>${data.verdict}</strong><br>
                <strong>Product:</strong> ${data.product}<br>
                <strong>Price Found:</strong> ${data.price}<br>
                <em>${data.reason}</em> 
            `;
        } else {
            resultBox.className = "scam";
            resultBox.innerHTML = `
                <strong>${data.verdict}</strong><br>
                <strong>Reason:</strong> ${data.reason}<br>
                <em>(Ziva could not verify this product.)</em>
            `;
        }

    } catch (error) {
        console.error("Error:", error);
        resultBox.className = "scam";
        resultBox.innerHTML = "<strong>❌ SYSTEM ERROR</strong><br>Could not reach the Ziva Cloud Server.<br>It might be sleeping (Free Tier). Try again in 30 seconds.";
        button.disabled = false;
        button.innerText = "Check Trust";
    }
}
