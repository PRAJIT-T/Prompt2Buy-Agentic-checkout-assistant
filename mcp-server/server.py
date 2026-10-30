import sys
import os
import asyncio
import json
from typing import Any

# ---------------------------------------------------------
# Allow MCP server to import the existing merchant backend
# ---------------------------------------------------------

BACKEND_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "merchant-backend")
)

if BACKEND_PATH not in sys.path:
    sys.path.insert(0, BACKEND_PATH)


# ---------------------------------------------------------
# MCP imports
# ---------------------------------------------------------

import mcp.server.stdio
import mcp.types as types

from mcp.server.lowlevel import Server
from mcp.server.context import ServerRequestContext


# ---------------------------------------------------------
# Merchant backend imports
# ---------------------------------------------------------

import httpx


# ---------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------

TOOLS = [

    types.Tool(
        name="search_catalog",
        description=(
            "Search the merchant product catalog using natural-language terms. "
            "The search understands product names, descriptions, categories, "
            "common category words such as audio and electronics, and singular "
            "or plural forms such as speaker and speakers. "
            "This is a read-only operation."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Natural-language product request, such as "
                        "'speakers' or 'wireless headphones'."
                    )
                },
                "max_price": {
                    "type": "number",
                    "description": "Optional maximum product price."
                },
            },
            "required": ["query"]
        }
    ),

    types.Tool(
        name="get_product_details",
        description=(
            "Get detailed information about a specific product. "
            "This is a read-only operation."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "product_id": {
                    "type": "string",
                    "description": "The product ID."
                }
            },
            "required": ["product_id"]
        }
    ),

    types.Tool(
        name="start_cart",
        description=(
            "Create a new empty shopping cart. "
            "This does not spend money."
        ),
        input_schema={
            "type": "object",
            "properties": {},
            "required": []
        }
    ),

    types.Tool(
        name="add_to_cart",
        description=(
            "Add a product to an existing shopping cart. "
            "This does not spend money."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "cart_id": {
                    "type": "string",
                    "description": "The shopping cart ID."
                },
                "product_id": {
                    "type": "string",
                    "description": "The product ID."
                },
                "quantity": {
                    "type": "integer",
                    "description": "Number of units to add."
                }
            },
            "required": [
                "cart_id",
                "product_id",
                "quantity"
            ]
        }
    ),

    types.Tool(
        name="get_cart",
        description=(
            "Get the current contents of a shopping cart. "
            "This is a read-only operation."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "cart_id": {
                    "type": "string",
                    "description": "The shopping cart ID."
                }
            },
            "required": ["cart_id"]
        }
    ),

        types.Tool(
        name="cancel_order",
        description=(
            "Cancel a pending order that has not been paid yet. "
            "Only orders with status 'pending' can be cancelled. "
            "This does not refund anything since no payment was made."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "order_id": {
                    "type": "string",
                    "description": "The order ID to cancel."
                }
            },
            "required": ["order_id"]
        }
    ),

    types.Tool(
        name="checkout",
        description=(
            "Checkout the shopping cart and create a Razorpay payment order. "
            "THIS IS THE ONLY TOOL THAT INITIATES THE PAYMENT FLOW. "
            "It must only be called after the user has explicitly confirmed "
            "the final cart contents and total amount. "
            "The merchant SpendCap is enforced. "
            "If the SpendCap is exceeded, checkout fails. "
            "Successful Razorpay order creation does NOT mean the customer "
            "has paid; it only creates the Razorpay payment order."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "cart_id": {
                    "type": "string",
                    "description": "The cart to checkout."
                }
            },
            "required": ["cart_id"]
        }
    ),

    types.Tool(
        name="get_audit_log",
        description=(
            "Get the full audit trail of every state-changing action "
            "on the merchant system: carts created, items added, orders "
            "created, payments verified, orders cancelled. Read-only."
        ),
        input_schema={
            "type": "object",
            "properties": {},
            "required": []
        }
    ),

    types.Tool(
        name="get_order_status",
        description=(
            "Get the current status of an order. "
            "This is a read-only operation."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "order_id": {
                    "type": "string",
                    "description": "The order ID."
                }
            },
            "required": ["order_id"]
        }
    )
]


# ---------------------------------------------------------
# List tools handler
# ---------------------------------------------------------

async def handle_list_tools(
    ctx: ServerRequestContext[Any],
    params: types.PaginatedRequestParams | None
) -> types.ListToolsResult:

    return types.ListToolsResult(
        tools=TOOLS
    )


# ---------------------------------------------------------
# Call tool handler
# ---------------------------------------------------------

async def handle_call_tool(
    ctx: ServerRequestContext[Any],
    params: types.CallToolRequestParams
) -> types.CallToolResult:

    try:

        arguments = params.arguments or {}

        # ---------------------------------------------
        # SEARCH CATALOG
        # ---------------------------------------------

        if params.name == "search_catalog":

            query = arguments.get("query", "")
            max_price = arguments.get("max_price")

            params = {
                "query": query
            }

            if max_price is not None:
                params["max_price"] = max_price

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "http://127.0.0.1:8000/products",
                    params=params
                )

            response.raise_for_status()

            data = response.json()

            return types.CallToolResult(
                content=[
                    types.TextContent(
                        type="text",
                        text=json.dumps(
                            data["products"],
                            default=str
                        )
                    )
                ]
            )


        # ---------------------------------------------
        # GET PRODUCT DETAILS
        # ---------------------------------------------

        elif params.name == "get_product_details":

            product_id = arguments["product_id"]

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"http://127.0.0.1:8000/products/{product_id}"
                )

            if response.status_code == 404:
                return types.CallToolResult(
                    content=[
                        types.TextContent(
                            type="text",
                            text=json.dumps({
                                "error": f"Product '{product_id}' not found."
                            })
                        )
                    ],
                    is_error=True
                )

            response.raise_for_status()

            product = response.json()

            return types.CallToolResult(
                content=[
                    types.TextContent(
                        type="text",
                        text=json.dumps(
                            product,
                            default=str
                        )
                    )
                ]
            )


        # ---------------------------------------------
        # START CART
        # ---------------------------------------------

        elif params.name == "start_cart":

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "http://127.0.0.1:8000/carts"
                )

            response.raise_for_status()

            result = response.json()

            return types.CallToolResult(
                content=[
                    types.TextContent(
                        type="text",
                        text=json.dumps(result)
                    )
                ]
            )


        # ---------------------------------------------
        # ADD TO CART
        # ---------------------------------------------

        elif params.name == "add_to_cart":

            cart_id = arguments["cart_id"]
            product_id = arguments["product_id"]
            quantity = arguments["quantity"]

            payload = {
                "product_id": product_id,
                "quantity": quantity
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"http://127.0.0.1:8000/carts/{cart_id}/items",
                    json=payload
                )

            response.raise_for_status()

            result = response.json()

            return types.CallToolResult(
                content=[
                    types.TextContent(
                        type="text",
                        text=json.dumps(result)
                    )
                ]
            )

        # ---------------------------------------------
        # GET CART
        # ---------------------------------------------

        elif params.name == "get_cart":

            cart_id = arguments["cart_id"]

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"http://127.0.0.1:8000/carts/{cart_id}"
                )

            response.raise_for_status()

            result = response.json()

            return types.CallToolResult(
                content=[
                    types.TextContent(
                        type="text",
                        text=json.dumps(result, default=str)
                    )
                ]
            )


        # ---------------------------------------------
        # CHECKOUT
        # ---------------------------------------------

        elif params.name == "checkout":

            cart_id = arguments["cart_id"]

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "http://127.0.0.1:8000/checkout",
                    params={"cart_id": cart_id}
                )

            response.raise_for_status()

            result = response.json()

            return types.CallToolResult(
                content=[
                    types.TextContent(
                        type="text",
                        text=json.dumps(result, default=str)
                    )
                ]
            )

                # ---------------------------------------------
        # CANCEL ORDER
        # ---------------------------------------------

        elif params.name == "cancel_order":

            order_id = arguments["order_id"]

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"http://127.0.0.1:8000/orders/{order_id}/cancel"
                )

            if response.status_code == 400:
                return types.CallToolResult(
                    content=[
                        types.TextContent(
                            type="text",
                            text=json.dumps({
                                "error": response.json().get("detail", "Cancel failed.")
                            })
                        )
                    ],
                    is_error=True
                )

            response.raise_for_status()

            result = response.json()

            return types.CallToolResult(
                content=[
                    types.TextContent(
                        type="text",
                        text=json.dumps(result, default=str)
                    )
                ]
            )

        elif params.name == "get_audit_log":

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "http://127.0.0.1:8000/audit-log"
                )

            response.raise_for_status()
            result = response.json()

            return types.CallToolResult(
                content=[
                    types.TextContent(
                        type="text",
                        text=json.dumps(result, default=str)
                    )
                ]
            )


        # ---------------------------------------------
        # ORDER STATUS
        # ---------------------------------------------

        elif params.name == "get_order_status":
            order_id = arguments["order_id"]

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"http://127.0.0.1:8000/orders/{order_id}/status"
                )

            response.raise_for_status()

            result = response.json()

            return types.CallToolResult(
                content=[
                    types.TextContent(
                        type="text",
                        text=json.dumps(result, default=str)
                    )
                ]
            )


        # ---------------------------------------------
        # UNKNOWN TOOL
        # ---------------------------------------------

        else:

            raise ValueError(
                f"Unknown tool: {params.name}"
            )


    except Exception as e:

        return types.CallToolResult(
            content=[
                types.TextContent(
                    type="text",
                    text=json.dumps({
                        "error": str(e)
                    })
                )
            ],
            is_error=True
        )


# ---------------------------------------------------------
# Create MCP server
# ---------------------------------------------------------

server = Server(
    "merchant-commerce",
    on_list_tools=handle_list_tools,
    on_call_tool=handle_call_tool
)


# ---------------------------------------------------------
# Run server using stdio
# ---------------------------------------------------------

async def main():

    async with mcp.server.stdio.stdio_server() as (
        read_stream,
        write_stream
    ):

        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())