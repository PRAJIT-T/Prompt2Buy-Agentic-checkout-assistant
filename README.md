# Prompt2Buy

### Agentic Shopping Assistant

*From prompt to payment.*

Prompt2Buy is a shopping agent you talk to. Tell it what you want, it searches a merchant catalog, manages your cart, and takes you through a Razorpay Test Mode payment, but only after you explicitly say yes.

Built for the **Razorpay AI Buildathon, Track 01: AI Growth & Agentic Commerce**.

---

## What it does

Instead of clicking through search, product pages, cart and checkout, you just chat:

```text
You:    I need wireless headphones under ₹1000
Agent:  (searches the catalog, suggests a few options)
You:    Add the second one to my cart
Agent:  (resolves "the second one" from the conversation and adds it)
You:    Checkout
Agent:  Here's your cart and total. Confirm to proceed?
```

The agent never makes up prices or stock. Everything it says about products, carts and orders comes from tool calls to the merchant backend.

It keeps conversation history, so references like "that", "this one" or "add it" work without you repeating product IDs.

---

## The rule I built around: the AI never moves money on its own

Letting an LLM near a payment flow is risky, so the safety checks live in the backend, not in the prompt.

- **Explicit confirmation.** Before checkout, the agent shows the final cart, quantities and total. Nothing happens until the user confirms.
- **Spend cap.** The merchant backend enforces a configured limit. If the total exceeds it, checkout fails, no matter what the model says.
- **Server-side payment verification.** The browser's word is never trusted. An order only becomes `PAID` after the backend verifies the payment itself.
- **Audit log.** Every state-changing action is recorded with a timestamp, so you can trace what happened and when.

---

## How a payment works

1. The user confirms the cart.
2. The buyer agent calls the MCP `checkout` tool.
3. The MCP server forwards the request to the merchant backend.
4. The backend creates a local order and a Razorpay order.
5. The user pays through Razorpay Checkout.
6. Razorpay returns the payment details to the backend.
7. The backend verifies them, and only then marks the order `PAID`.

Creating a Razorpay order doesn't mean the customer has paid. That's why step 7 exists.

### What the backend checks before marking an order paid

- The local order exists
- The Razorpay order ID matches the one it created
- The payment signature is valid
- The payment belongs to that Razorpay order
- The paid amount matches the local order amount
- The payment status is `captured`

### Order states

```text
PENDING --(payment verified)--> PAID
PENDING --(cancelled)---------> CANCELLED
```

Only unpaid `PENDING` orders can be cancelled. Cancelling a paid order would need a proper refund flow, which this project doesn't implement.

---

## MCP tools

The agent doesn't touch the merchant system directly. It goes through an MCP server that exposes a fixed set of operations:

| Tool | Purpose |
|------|---------|
| `search_catalog` | Search products |
| `get_product_details` | Get details for one product |
| `start_cart` | Create a cart |
| `add_to_cart` | Add an item |
| `get_cart` | View the cart |
| `checkout` | Create the order and start payment |
| `cancel_order` | Cancel an unpaid order |
| `get_order_status` | Check an order's status |
| `get_audit_log` | Read the audit trail |

---

## Architecture

```text
User
  |
  v
Chat UI (browser)
  |
  v
buyer-agent API (:9000)
  |
  v
Buyer Agent (local Gemma)
  |
  | MCP
  v
MCP Server
  |
  | HTTP
  v
Merchant Backend (:8000)
  |-- Catalog
  |-- Cart
  |-- Orders --> Audit log
  |
  v
Razorpay (Test Mode) --> Razorpay Checkout
  |
  v
Server-side verification --> Order marked PAID
```

---

## Project structure

```text
prompt2buy/
├── buyer-agent/
│   ├── api.py
│   ├── agent.py
│   └── static/
│       ├── index.html
│       ├── style.css
│       └── app.js
│
├── mcp-server/
│   └── server.py
│
├── merchant-backend/
│   ├── api.py
│   ├── audit.py
│   ├── cart.py
│   ├── catalog.py
│   ├── config.py
│   ├── models.py
│   ├── orders.py
│   ├── razorpay_client.py
│   └── data/
│       └── catalog.json
│
├── .env
├── .gitignore
└── README.md
```

---

## Limitations

- Payments run in **Razorpay Test Mode** only, so no real money moves.
- No refund flow, so paid orders can't be cancelled.
- The catalog is a static JSON file, not a live merchant inventory.
