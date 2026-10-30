import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI

from agents import (
    Agent,
    Runner,
    OpenAIChatCompletionsModel,
    SQLiteSession,
    set_tracing_disabled,
)

from agents.mcp import MCPServerStdio


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MCP_SERVER_PATH = PROJECT_ROOT / "mcp-server" / "server.py"
load_dotenv(PROJECT_ROOT / ".env")

# Our model is local, so OpenAI tracing is unnecessary.
set_tracing_disabled(True)


class BuyerAgent:
    def __init__(self):
        self.client = AsyncOpenAI(
            base_url="http://127.0.0.1:9931/v1",
            api_key="local",
        )

        # Keeps conversation history across chat requests.
        self.session = SQLiteSession("buyer_demo")

        self.mcp_server = None
        self.agent = None

    async def start(self):
        """
        Start the MCP connection and create the AI Buyer agent.
        """

        self.mcp_server = MCPServerStdio(
            name="Merchant MCP Server",
            params={
                "command": sys.executable,
                "args": [str(MCP_SERVER_PATH)],
                "cwd": str(PROJECT_ROOT),
            },
        )

        await self.mcp_server.__aenter__()

        self.agent = Agent(
            name="AI Buyer",

            instructions="""
You are an AI shopping assistant.

Your job is to help the user discover products, manage their shopping cart,
and complete purchases using the available merchant MCP tools.

Rules:
- Always use the MCP tools to obtain real product, cart, and order information.
- Never invent products, prices, stock, cart contents, order IDs, or order statuses.
- Remember the context of the conversation and resolve references such as
  "that", "this product", and "add it" using previous messages.
- Do not ask the user for internal IDs such as product IDs, cart IDs, or order IDs
  when you already have the required information from the conversation or tools.

Cart display:
- When the user asks about their cart, retrieve the actual cart information
  using the appropriate MCP tool.
- Present the cart as a concise shopping summary.
- Use this format:

  Your Cart

  - Product Name x quantity - ₹price

  Total: ₹total

- If the cart is empty, clearly say that the cart is empty.
- Do not unnecessarily ask whether the user wants to checkout after every
  cart lookup. Only mention checkout when it is relevant to the conversation.

Checkout:
- Before calling checkout, clearly show the final cart contents and total.
- Ask the user for explicit confirmation before calling checkout.
- If the user clearly confirms checkout after the final cart summary,
  treat that as explicit confirmation.
- Once checkout is called, report the actual order information returned by
  the merchant system.
- Never claim that an order is paid unless the merchant system reports it
  as paid.
- If the order is pending payment, clearly tell the user that payment still
  needs to be completed.
- Format responses as concise, readable Markdown. Use short paragraphs and
  bullet lists when listing products; do not write dense walls of text.
- For checkout failures, state that payment could not be started and that no
  successful payment has been confirmed. Never claim that money was charged
  unless the merchant backend confirms a captured payment.
""",

            model=OpenAIChatCompletionsModel(
                model=os.getenv("LLM_MODEL_ID", "gemma-local"),
                openai_client=self.client,
            ),

            mcp_servers=[self.mcp_server],
        )

    async def chat(self, user_message: str) -> str:
        """
        Send one user message to the AI Buyer and return its response.
        """

        if self.agent is None:
            raise RuntimeError("BuyerAgent has not been started.")

        result = await Runner.run(
            self.agent,
            user_message,
            session=self.session,
        )

        return result.final_output

    async def stop(self):
        """
        Cleanly close the MCP connection.
        """

        if self.mcp_server is not None:
            await self.mcp_server.__aexit__(None, None, None)

        await self.client.close()


async def main():

    buyer = BuyerAgent()

    await buyer.start()

    try:
        while True:

            user_message = input("\nYou: ")

            if user_message.lower() in ["exit", "quit"]:
                break

            response = await buyer.chat(user_message)

            print("\nAI:", response)

    finally:
        await buyer.stop()


if __name__ == "__main__":
    asyncio.run(main())