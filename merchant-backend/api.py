from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
import re

from config import RAZORPAY_KEY_ID
from cart import create_cart, add_item, get_cart, get_cart_total_price
from orders import (
    checkout,
    get_order_status,
    get_order,
    get_order_by_razorpay_id,
    update_order_status,
    cancel_order,
    request_return,
    simulate_return_refund,
)
from catalog import get_all_products, get_product_by_id
from models import OrderStatus
from razorpay_client import RazorpayClient
from audit import get_audit_log


app = FastAPI(
    title="Merchant Commerce API",
    description="HTTP API for the merchant backend",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:9000", "http://localhost:9000"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)

class AddToCartRequest(BaseModel):
    product_id: str
    quantity: int

class PaymentVerificationRequest(BaseModel):
    razorpay_payment_id: str
    razorpay_order_id: str
    razorpay_signature: str

class ReturnRequestBody(BaseModel):
    reason: str = Field(min_length=3, max_length=250)


SEARCH_STOP_WORDS = {
    "a", "an", "and", "below", "buy", "find", "for", "me", "of",
    "please", "product", "products", "show", "something", "the", "under",
    "rupee", "rupees", "want", "with", "within",
}

SEARCH_CATEGORY_ALIASES = {
    "audio": {"Audio", "Headphones"},
    "electronic": {"Audio", "Headphones", "Wearables", "Workspace"},
    "electronics": {"Audio", "Headphones", "Wearables", "Workspace"},
    "earbud": {"Headphones"},
    "earbuds": {"Headphones"},
    "headphone": {"Headphones"},
    "headphones": {"Headphones"},
    "music": {"Audio", "Headphones"},
    "sound": {"Audio", "Headphones"},
    "speaker": {"Audio"},
    "speakers": {"Audio"},
    "watch": {"Wearables"},
    "watches": {"Wearables"},
}


def _singularize(word: str) -> str:
    if len(word) > 4 and word.endswith("ies"):
        return f"{word[:-3]}y"
    if len(word) > 4 and word.endswith("es"):
        return word[:-2]
    if len(word) > 3 and word.endswith("s"):
        return word[:-1]
    return word


def _search_terms(value: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", value.casefold())
    return {
        _singularize(word)
        for word in words
        if word not in SEARCH_STOP_WORDS and not word.isdigit()
    }


def _product_matches_query(query: str, product) -> bool:
    terms = _search_terms(query)
    if not terms:
        return True

    product_text = " ".join(
        (product.name, product.description, product.category)
    ).casefold()
    product_terms = _search_terms(product_text)

    for term in terms:
        if term in SEARCH_CATEGORY_ALIASES:
            if product.category in SEARCH_CATEGORY_ALIASES[term]:
                return True
        elif term in product_terms:
            return True

    return False


@app.get("/products")
def get_products(
    query: str = "",
    max_price: float | None = None,
    category: str | None = None,
):
    products = get_all_products()

    results = []

    for product in products:
        matches_query = _product_matches_query(query, product)

        matches_price = (
            max_price is None
            or product.price <= max_price
        )
        matches_category = (
            category is None
            or product.category.casefold() == category.casefold()
        )

        if matches_query and matches_price and matches_category:
            results.append(product.model_dump())

    return {
        "products": results
    }


@app.get("/products/{product_id}")
def get_product(product_id: str):
    product = get_product_by_id(product_id)

    if product is None:
        raise HTTPException(
        status_code=404,
        detail=f"Product '{product_id}' not found."
    )

    return product.model_dump()

@app.post("/carts")
def start_cart():
    cart = create_cart()

    return {
        "cart_id": cart.id,
        "items": []
    }

@app.post("/carts/{cart_id}/items")
def add_cart_item(
    cart_id: str,
    request: AddToCartRequest
):
    cart = add_item(
        cart_id,
        request.product_id,
        request.quantity
    )

    return {
        "cart_id": cart_id,
        "items": [
            item.model_dump()
            for item in cart.values()
        ],
        "total_amount": get_cart_total_price(cart)
    }

@app.get("/carts/{cart_id}")
def get_cart_api(cart_id: str):
    try:
        cart = get_cart(cart_id)

        return {
            "cart_id": cart_id,
            "items": [
                item.model_dump()
                for item in cart.values()
            ],
            "total_amount": get_cart_total_price(cart)
        }

    except ValueError as e:
        raise HTTPException(
            status_code=404,
            detail=str(e)
        )

@app.get("/audit-log")
def audit_log():
    return get_audit_log()
   
@app.post("/checkout")
def checkout_cart(cart_id: str):
    try:
        return checkout(cart_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/orders/{order_id}/status")
def get_order_status_api(order_id: str):
    try:
        return get_order_status(order_id)
    except ValueError as e:
        raise HTTPException(
            status_code=404,
            detail=str(e)
        )

@app.post("/orders/{order_id}/cancel")
def cancel_order_api(order_id: str):
    try:
        order = cancel_order(order_id)
        return {"order_id": order.id, "status": order.status.value}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/orders/{order_id}/returns")
def create_return_request(order_id: str, request: ReturnRequestBody):
    try:
        return request_return(order_id, request.reason)
    except ValueError as e:
        message = str(e)
        status_code = 404 if "not found" in message.lower() else 400
        raise HTTPException(status_code=status_code, detail=message)


@app.post("/returns/{return_id}/simulate-refund")
def simulate_refund(return_id: str):
    try:
        return simulate_return_refund(return_id)
    except ValueError as e:
        message = str(e)
        status_code = 404 if "not found" in message.lower() else 400
        raise HTTPException(status_code=status_code, detail=message)


@app.get("/orders/{order_id}/invoice", response_class=HTMLResponse)
def invoice(order_id: str):
    try:
        order = get_order(order_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    if order.status != OrderStatus.PAID:
        raise HTTPException(
            status_code=400,
            detail=f"Invoice only available for paid orders. Current status: {order.status.value}"
        )

    rows = "".join(
        f"<tr><td>{item.product_id}</td><td>{item.quantity}</td><td>Rs. {item.price:.2f}</td><td>Rs. {item.price * item.quantity:.2f}</td></tr>"
        for item in order.items
    )

    return f"""<!DOCTYPE html>
    <html><head><meta charset="UTF-8"><title>Invoice {order.id}</title>
    <style>
    body {{ font-family: 'Segoe UI', Arial, sans-serif; background:#eef1f5; padding:40px; color:#1a1a1a; }}
    .sheet {{ max-width:640px; margin:auto; background:#fff; padding:48px; border-radius:4px; box-shadow:0 1px 4px rgba(0,0,0,0.08); }}
    .top {{ display:flex; justify-content:space-between; align-items:flex-start; border-bottom:2px solid #1a1a1a; padding-bottom:24px; margin-bottom:24px; }}
    .brand {{ font-size:22px; font-weight:700; letter-spacing:0.5px; }}
    .invoice-label {{ text-align:right; }}
    .invoice-label h1 {{ font-size:26px; margin:0; letter-spacing:1px; }}
    .invoice-label p {{ margin:4px 0 0; color:#666; font-size:13px; }}
    .meta {{ display:flex; justify-content:space-between; margin-bottom:32px; font-size:13px; color:#444; }}
    .meta div {{ line-height:1.6; }}
    .meta strong {{ color:#111; }}
    table {{ width:100%; border-collapse:collapse; margin-bottom:24px; }}
    th {{ text-align:left; font-size:12px; text-transform:uppercase; letter-spacing:0.5px; color:#888; border-bottom:1px solid #ddd; padding:8px 6px; }}
    td {{ padding:12px 6px; border-bottom:1px solid #eee; font-size:14px; }}
    .totals {{ display:flex; justify-content:flex-end; }}
    .totals table {{ width:260px; }}
    .totals td {{ border:none; padding:6px; }}
    .grand {{ font-size:18px; font-weight:700; border-top:2px solid #1a1a1a !important; }}
    .footer {{ margin-top:36px; padding-top:16px; border-top:1px solid #eee; font-size:12px; color:#999; text-align:center; }}
    </style>
    </head>
    <body>
    <div class="sheet">
        <div class="top">
        <div class="brand">AI Buyer Merchant</div>
        <div class="invoice-label">
            <h1>INVOICE</h1>
            <p>{order.id}</p>
        </div>
        </div>

        <div class="meta">
        <div><strong>Billed to</strong><br>Customer ({order.customer_id})</div>
        <div style="text-align:right;"><strong>Date</strong><br>{order.updated_at.strftime('%d %b %Y, %I:%M %p')}</div>
        </div>

        <table>
        <tr><th>Item</th><th>Qty</th><th>Unit Price</th><th>Amount</th></tr>
        {rows}
        </table>

        <div class="totals">
        <table>
            <tr><td>Subtotal</td><td style="text-align:right;">Rs. {order.total_amount:.2f}</td></tr>
            <tr class="grand"><td>Total Paid</td><td style="text-align:right;">Rs. {order.total_amount:.2f}</td></tr>
        </table>
        </div>

        <div class="footer">Payment status: PAID &middot; Thank you for your purchase.</div>
    </div>
    </body>
    </html>"""

@app.get("/pay/{order_id}", response_class=HTMLResponse)
def payment_page(order_id: str):
    try:
        order = get_order(order_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    

    if order.status.value != "pending":
        raise HTTPException(
            status_code=400,
            detail=f"Order is not pending. Current status: {order.status.value}"
        )

    razorpay_order_id = order.razorpay_order_id
    amount_paise = int(round(order.total_amount * 100))

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Secure Checkout</title>

        <script src="https://checkout.razorpay.com/v1/checkout.js"></script>

        <style>
            * {{
                box-sizing: border-box;
            }}

            body {{
                margin: 0;
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                font-family: Arial, sans-serif;
                background: #f5f7fb;
                color: #222;
            }}

            .card {{
                width: 420px;
                max-width: 90%;
                background: white;
                padding: 36px;
                border-radius: 18px;
                box-shadow: 0 12px 40px rgba(0,0,0,0.10);
                text-align: center;
            }}

            .icon {{
                font-size: 42px;
                margin-bottom: 16px;
            }}

            h1 {{
                margin: 0 0 10px;
                font-size: 24px;
            }}

            .subtitle {{
                color: #666;
                margin-bottom: 24px;
            }}

            .amount {{
                font-size: 30px;
                font-weight: bold;
                margin: 20px 0;
            }}

            .status {{
                color: #777;
                font-size: 14px;
            }}

            .fallback {{
                display: none;
                margin-top: 20px;
                padding: 12px 18px;
                border: none;
                border-radius: 8px;
                background: #222;
                color: white;
                cursor: pointer;
                font-size: 15px;
            }}
        </style>
    </head>

    <body>

        <div class="card">
            <div class="icon" aria-hidden="true">Secure</div>

            <h1>Secure Checkout</h1>

            <div class="subtitle">
                Your payment is being securely prepared.
            </div>

            <div class="amount">
                ₹{order.total_amount:.2f}
            </div>

            <div class="status" id="status">
                Opening Razorpay Checkout...
            </div>

            <button class="fallback" id="fallback">
                Open Secure Checkout
            </button>
        </div>

        <script>
            const options = {{
                key: "{RAZORPAY_KEY_ID}",
                amount: {amount_paise},
                currency: "INR",
                name: "AI Buyer Merchant",
                description: "AI Buyer Agent Purchase",
                order_id: "{razorpay_order_id}",

                handler: async function(response) {{

                    document.getElementById("status").textContent =
                        "Verifying your payment...";

                    try {{

                        const verificationResponse = await fetch(
                            "/payments/verify",
                            {{
                                method: "POST",
                                headers: {{
                                    "Content-Type": "application/json"
                                }},
                                body: JSON.stringify({{
                                    razorpay_payment_id:
                                        response.razorpay_payment_id,

                                    razorpay_order_id:
                                        response.razorpay_order_id,

                                    razorpay_signature:
                                        response.razorpay_signature
                                }})
                            }}
                        );

                        const result =
                            await verificationResponse.json();

                        if (!verificationResponse.ok) {{
                            document.getElementById("status").textContent =
                                "Payment verification failed.";

                            alert(
                                "Payment verification failed: " +
                                result.detail
                            );

                            return;
                        }}

                        // Tell the original AI chat that payment
                        // was successfully verified by our server.
                        if (window.opener && !window.opener.closed) {{
                                    window.opener.postMessage(
                                    {{
                                        type: "PAYMENT_SUCCESS",
                                        orderId: result.order_id,
                                        paymentId: result.razorpay_payment_id
                                    }}, "*");
                                }}

                                document.body.innerHTML = `
                                    <div style="
                                        min-height:100vh;
                                        display:flex;
                                        align-items:center;
                                        justify-content:center;
                                        font-family:Arial,sans-serif;
                                        background:linear-gradient(135deg,#e8f9f0,#f5f7fb);
                                    ">
                                        <div style="
                                            background:white;
                                            padding:44px;
                                            border-radius:20px;
                                            text-align:center;
                                            box-shadow:0 16px 45px rgba(16,185,129,0.18);
                                            border-top:5px solid #10b981;
                                        ">
                                            <div style="
                                                width:64px;height:64px;
                                                border-radius:50%;
                                                background:#10b981;
                                                color:white;
                                                display:flex;align-items:center;justify-content:center;
                                                font-size:32px;
                                                margin:0 auto 18px;
                                            ">✓</div>

                                            <h1 style="color:#111;margin-bottom:8px;">Payment Verified</h1>
                                            <p style="color:#555;">Your payment was successfully verified.</p>
                                            <p style="margin-top:14px;">Order: <strong>${{result.order_id}}</strong></p>
                                            <p style="color:#999;font-size:13px;margin-top:16px;">you can close this page and return to your Buyer assistan...</p>
                                        </div>
                                    </div>
                                `;

                    }} catch (error) {{

                        document.getElementById("status").textContent =
                            "Unable to verify payment.";

                        alert(
                            "Something went wrong while verifying payment."
                        );
                    }}
                }},

                modal: {{
                    ondismiss: function() {{
                        document.getElementById("status").textContent =
                            "Payment was not completed.";

                        // Do not mark the order as failed.
                        // It remains PENDING and can be retried.
                    }}
                }},

                theme: {{
                    color: "#222222"
                }}
            }};

            const rzp = new Razorpay(options);
            rzp.on('payment.failed', function (response) {{
            document.getElementById("status").textContent = "Payment failed.";
            if (window.opener) {{
                window.opener.postMessage({{
                    type: "PAYMENT_FAILED",
                    orderId: "{order.id}",
                    reason: response.error.description
                            }}, "*");
                        }}
                    }});

            // Automatically open Razorpay.
            window.onload = function() {{
                rzp.open();

                // Fallback in case the browser blocks automatic opening.
                setTimeout(function() {{
                    document.getElementById("fallback").style.display =
                        "inline-block";
                }}, 2500);
            }};

            document.getElementById("fallback").onclick = function() {{
                rzp.open();
            }};
        </script>

    </body>
    </html>
    """

@app.post("/payments/verify")
def verify_payment(request: PaymentVerificationRequest):

    # 1. Find our local order
    try:
        order = get_order_by_razorpay_id(request.razorpay_order_id)
    except ValueError as e:
        raise HTTPException(
            status_code=404,
            detail=str(e)
        )

    # 2. Verify that the Razorpay order belongs to our local order
    if order.razorpay_order_id != request.razorpay_order_id:
        raise HTTPException(
            status_code=400,
            detail="Razorpay order ID does not match local order."
        )

    # 3. Verify Razorpay signature
    razorpay_client = RazorpayClient()

    try:
        razorpay_client.verify_payment_signature(
            razorpay_order_id=order.razorpay_order_id,
            razorpay_payment_id=request.razorpay_payment_id,
            razorpay_signature=request.razorpay_signature
        )
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Payment signature verification failed."
        )

    # 4. Fetch the actual payment from Razorpay
    payment = razorpay_client.fetch_payment(
        request.razorpay_payment_id
    )

    if "error" in payment:
        raise HTTPException(
            status_code=502,
            detail="Unable to fetch payment from Razorpay."
        )

    # 5. Confirm the payment belongs to the expected Razorpay order
    if payment.get("order_id") != order.razorpay_order_id:
        raise HTTPException(
            status_code=400,
            detail="Payment does not belong to this order."
        )

    # 6. Confirm the amount
    expected_amount = int(round(order.total_amount * 100))

    if payment.get("amount") != expected_amount:
        raise HTTPException(
            status_code=400,
            detail="Payment amount does not match order amount."
        )

    # 7. Confirm Razorpay says the payment is captured
    if payment.get("status") != "captured":
        raise HTTPException(
            status_code=400,
            detail=f"Payment is not captured. Status: {payment.get('status')}"
        )

    # 8. Only now mark our local order as PAID
    updated_order = update_order_status(
        order.id,
        OrderStatus.PAID
    )

    return {
        "success": True,
        "order_id": updated_order.id,
        "status": updated_order.status.value,
        "razorpay_payment_id": request.razorpay_payment_id
    }