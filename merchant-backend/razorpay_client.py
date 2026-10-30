import os
import razorpay
import uuid
from config import RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET, require_razorpay_credentials

class RazorpayClient:
    """
    A client to interact with the Razorpay payment gateway.
    This class encapsulates all external API calls.
    """
    def __init__(self):
        """Initialize the gateway client only when credentials are configured."""
        require_razorpay_credentials()
        self.client = razorpay.Client(
            auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET)
        )

    def create_order(self, amount: float, currency: str = "INR") -> dict:
        """
        Creates a new order on Razorpay.

        Args:
            amount: The amount to charge in the smallest currency unit (e.g., paise for INR).
            currency: The currency code (e.g., "INR").

        Returns:
            A dictionary containing the order details from Razorpay.
        """
        try:
            order = self.client.order.create(
                data={
                "amount":int(amount),
                "currency":currency,
                "receipt": f"test_{uuid.uuid4().hex[:12]}" 
                }
            )
            return order
        except Exception as e:
            # Keep provider diagnostics in the backend terminal, not the chat.
            print(f"Razorpay order creation failed ({type(e).__name__}): {e}")
            return {
                "error": (
                    "Razorpay could not create the payment order. Check that "
                    "the Key ID and Key Secret are a matching Test Mode pair."
                )
            }

    def verify_payment_signature(
        self,
        razorpay_order_id: str,
        razorpay_payment_id: str,
        razorpay_signature: str
    ) -> bool:
        """ Verifies that the payment response came from Razorpay
        and was not tampered with.
        Returns:
            True if the signature is valid.
            Raises an exception if verification fails. """
        
        self.client.utility.verify_payment_signature({
            "razorpay_order_id": razorpay_order_id,
            "razorpay_payment_id": razorpay_payment_id,
            "razorpay_signature": razorpay_signature
        })

        return True

    def fetch_payment(self, payment_id: str) -> dict:
        """
        Fetches the actual Razorpay Payment object using its payment ID.

        This is used after signature verification to check
        the actual payment status.
        """
        try:
            payment = self.client.payment.fetch(payment_id)
            return payment
        except Exception as e:
            print(f"Error fetching payment: {e}")
            return {"error": str(e)}

# Example usage (for testing purposes, not part of the final module)
if __name__ == "__main__":
    # NOTE: This block will fail unless RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET are set in the environment
    # and a valid API key is used.
    print("--- Razorpay Client Test ---")
    try:
        client = RazorpayClient()
        # Mock amount for testing
        test_amount = 10000 # 100 INR
        print(f"Attempting to create a test order for {test_amount} paise...")
        # order_data = client.create_order(test_amount)
        # print("Order created successfully (mock):", order_data)
    except Exception as e:
        print(f"Could not initialize client: {e}")
        print("Please ensure RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET are set in config.py or environment variables.")