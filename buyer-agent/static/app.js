const chat = document.getElementById("chat");
const input = document.getElementById("messageInput");
const pixelCaret = document.querySelector(".pixel-caret");
const sendButton = document.getElementById("sendButton");
const promptButtons = document.querySelectorAll("[data-prompt]");
const cartToggle = document.getElementById("cartToggle");
const cartCard = document.getElementById("cartCard");
const merchantOrigin = "http://127.0.0.1:8000";
const productGrid = document.getElementById("productGrid");
const categoryFilters = document.getElementById("categoryFilters");
const catalogCount = document.getElementById("catalogCount");
const returnForm = document.getElementById("returnForm");
const returnResult = document.getElementById("returnResult");
const simulateRefundButton = document.getElementById("simulateRefundButton");
let catalogProducts = [];
let selectedCategory = "All";
let activeReturnId = null;

function updatePixelCaret() {
    const styles = getComputedStyle(input);
    const canvas = updatePixelCaret.canvas || (updatePixelCaret.canvas = document.createElement("canvas"));
    const context = canvas.getContext("2d");
    if (!context) return;
    context.font = styles.font;
    const textWidth = context.measureText(input.value.slice(0, input.selectionStart || 0)).width;
    const left = parseFloat(styles.paddingLeft) + textWidth - input.scrollLeft;
    pixelCaret.style.left = `${Math.max(parseFloat(styles.paddingLeft), left)}px`;
}

["input", "keyup", "click", "focus"].forEach(eventName => {
    input.addEventListener(eventName, updatePixelCaret);
});

cartToggle.addEventListener("click", () => {
    requestCart();
});

cartCard.addEventListener("click", requestCart);


function renderCatalog() {
    const categories = ["All", ...new Set(catalogProducts.map(product => product.category || "General"))];
    categoryFilters.replaceChildren();

    categories.forEach(category => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = `category-filter${category === selectedCategory ? " active" : ""}`;
        button.textContent = category;
        button.addEventListener("click", () => {
            selectedCategory = category;
            renderCatalog();
        });
        categoryFilters.appendChild(button);
    });

    const visibleProducts = selectedCategory === "All"
        ? catalogProducts
        : catalogProducts.filter(product => (product.category || "General") === selectedCategory);

    catalogCount.textContent = `${visibleProducts.length} products`;
    productGrid.replaceChildren();

    if (!visibleProducts.length) {
        const empty = document.createElement("p");
        empty.className = "catalog-message";
        empty.textContent = "No products in this category yet.";
        productGrid.appendChild(empty);
        return;
    }

    visibleProducts.forEach(product => {
        const card = document.createElement("article");
        card.className = "catalog-product-card";

        const image = document.createElement("img");
        image.className = "catalog-product-image";
        image.src = product.image_url || "";
        image.alt = product.name;
        image.loading = "lazy";
        image.onerror = () => {
            image.removeAttribute("src");
            image.classList.add("image-unavailable");
            image.alt = "Product image unavailable";
        };

        const detail = document.createElement("div");
        detail.className = "catalog-product-details";
        const category = document.createElement("small");
        category.className = "product-category";
        category.textContent = product.category || "General";
        const name = document.createElement("h4");
        name.textContent = product.name;
        const description = document.createElement("p");
        description.textContent = product.description;
        const bottom = document.createElement("div");
        bottom.className = "catalog-product-bottom";
        const price = document.createElement("strong");
        price.textContent = `₹${Number(product.price).toFixed(2)}`;
        const askButton = document.createElement("button");
        askButton.className = "ask-product-button";
        askButton.type = "button";
        askButton.textContent = "Ask assistant";
        askButton.addEventListener("click", () => {
            input.value = `Tell me about ${product.name}`;
            input.focus();
            sendMessage();
        });
        bottom.append(price, askButton);
        detail.append(category, name, description, bottom);
        card.append(image, detail);
        productGrid.appendChild(card);
    });
}

async function loadCatalog() {
    try {
        const response = await fetch(`${merchantOrigin}/products`);
        if (!response.ok) throw new Error("Catalog request failed");
        const data = await response.json();
        catalogProducts = data.products || [];
        renderCatalog();
    } catch (error) {
        catalogCount.textContent = "Unavailable";
        productGrid.replaceChildren();
        const message = document.createElement("p");
        message.className = "catalog-message";
        message.textContent = "Could not load products. Make sure the merchant backend is running on port 8000.";
        productGrid.appendChild(message);
    }
}

async function requestDemoReturn(event) {
    event.preventDefault();
    returnResult.textContent = "Submitting return request";
    simulateRefundButton.hidden = true;
    simulateRefundButton.disabled = false;
    activeReturnId = null;
    const orderId = document.getElementById("returnOrderId").value.trim();
    const reason = document.getElementById("returnReason").value;

    try {
        const response = await fetch(`${merchantOrigin}/orders/${encodeURIComponent(orderId)}/returns`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ reason })
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "Could not create return request.");
        activeReturnId = data.return_id;
        if (data.status === "simulated_refunded") {
            returnResult.textContent = `Return ${data.return_id} for ${data.order_id} was already simulated. Estimated amount: ₹${Number(data.refund_amount).toFixed(2)}. No real refund was sent.`;
            simulateRefundButton.hidden = true;
        } else {
            returnResult.textContent = `Return ${data.return_id} created for ${data.order_id}. Estimated demo refund: ₹${Number(data.refund_amount).toFixed(2)}. No real refund has been sent.`;
            simulateRefundButton.hidden = false;
        }
    } catch (error) {
        returnResult.textContent = error.message;
    }
}

async function simulateDemoRefund() {
    if (!activeReturnId) return;
    simulateRefundButton.disabled = true;
    returnResult.textContent = "Simulating refund";
    try {
        const response = await fetch(`${merchantOrigin}/returns/${encodeURIComponent(activeReturnId)}/simulate-refund`, {
            method: "POST"
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "Could not simulate refund.");
        returnResult.textContent = `Demo completed for ${data.return_id}: ₹${Number(data.refund_amount).toFixed(2)} marked as simulated. No real money moved.`;
        simulateRefundButton.hidden = true;
    } catch (error) {
        returnResult.textContent = error.message;
        simulateRefundButton.disabled = false;
    }
}


function addMessage(text, type , showPayButton= true) {
    const message = document.createElement("div");
    message.className = `message ${type}`;

    const avatar = document.createElement("div");
    avatar.className = "avatar";
    avatar.textContent = type === "user" ? "You" : "AI";

    const bubble = document.createElement("div");
    bubble.className = "bubble";

    // Find the real Order ID
    const orderMatch = text.match(/\bORD-[a-zA-Z0-9-]+\b/);
    const isPaymentPrompt = /pay|checkout|complete.*payment/i.test(text) && !/error|failed|cancel|audit/i.test(text);

    if (orderMatch && showPayButton && isPaymentPrompt) {
        const orderId = orderMatch[0];

        // Remove placeholder if AI used one
        let displayText = text.replace(
            /\[[^\]]*\]\([^)]*\)/g,
            ""
        ).trim();

        bubble.appendChild(
            document.createTextNode(displayText)
        );

        // Payment button
        const link = document.createElement("a");

        link.href = "#";
        link.textContent = "Pay securely with Razorpay";
        link.className = "payment-button";

        link.onclick = function(event) {
            event.preventDefault();

            const paymentUrl = `${merchantOrigin}/pay/${orderId}`;

            window.open(
                paymentUrl,
                "razorpay_payment",
                "width=500,height=750"
            );
        };

        bubble.appendChild(link);

    } else {
        bubble.textContent = text;
    }

    message.appendChild(avatar);
    message.appendChild(bubble);

    chat.appendChild(message);
    chat.scrollTop = chat.scrollHeight;
}


async function sendMessage() {

    const message = input.value.trim();

    if (!message) {
        return;
    }


    // Show user's message
    addMessage(message, "user");


    // Clear input
    input.value = "";


    // Disable while AI is responding
    sendButton.disabled = true;
    input.disabled = true;


    try {

        const response = await fetch("/chat", {

            method: "POST",

            headers: {
                "Content-Type": "application/json"
            },

            body: JSON.stringify({
                message: message
            })

        });


        const data = await response.json();


        if (!response.ok) {
            throw new Error(data.detail || "Request failed");
        }


        // Show AI response
        addMessage(data.response, "ai");


    } catch (error) {

        addMessage(
            "Sorry, something went wrong: " + error.message,
            "ai"
        );

    } finally {

        sendButton.disabled = false;
        input.disabled = false;

        input.focus();
    }
}

function requestCart() {
    input.value = "Show me my cart";
    input.focus();
    sendMessage();
}


sendButton.addEventListener("click", sendMessage);


input.addEventListener("keydown", function(event) {

    if (event.key === "Enter") {
        sendMessage();
    }

});

// Receive verified payment confirmation
// from the Razorpay payment window

window.addEventListener("message", function(event) {

    if (!event.data || (event.data.type !== "PAYMENT_SUCCESS" && event.data.type !== "PAYMENT_FAILED")) {
        return;
    }

    if (!event.data) {
        return;
    }

    if (event.data.type === "PAYMENT_SUCCESS") {

        const orderId = event.data.orderId;

        addMessage(
            `-----Payment successful!-----\n\n` +
            `Your order ${orderId} has been paid and confirmed.\n\n` +
            `Thankyou for purchasing!`,
            "ai",
            false
        );
        const invoiceLink = document.createElement("a");
        invoiceLink.href = `${merchantOrigin}/orders/${orderId}/invoice`;
        invoiceLink.target = "_blank";
        invoiceLink.textContent = "Download invoice";
        invoiceLink.style.display = "inline-block";
        invoiceLink.style.marginTop = "8px";
        invoiceLink.style.color = "#222";
        chat.lastElementChild.querySelector(".bubble").appendChild(document.createElement("br"));
        chat.lastElementChild.querySelector(".bubble").appendChild(invoiceLink);
    }
    if (event.data.type === "PAYMENT_FAILED") {
        addMessage(
            `Payment failed: ${event.data.reason}\n\nThe order is still pending — you can try paying again.`,
            "ai",
            false
        );
    }

});

promptButtons.forEach((button) => {
    button.addEventListener("click", () => {
        input.value = button.dataset.prompt;
        input.focus();
        sendMessage();
    });
});

if (returnForm) returnForm.addEventListener("submit", requestDemoReturn);
if (simulateRefundButton) simulateRefundButton.addEventListener("click", simulateDemoRefund);
loadCatalog();
