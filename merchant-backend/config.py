import os
from pathlib import Path

from dotenv import load_dotenv

ENV_FILE = Path(__file__).resolve().with_name(".env")
load_dotenv(ENV_FILE)

RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "").strip()
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "").strip()
SPEND_CAP = int(os.getenv("SPEND_CAP", "5000"))


def require_razorpay_credentials() -> None:
    """Fail with a clear configuration error before attempting a payment."""
    missing = []
    if not RAZORPAY_KEY_ID:
        missing.append("RAZORPAY_KEY_ID")
    if not RAZORPAY_KEY_SECRET:
        missing.append("RAZORPAY_KEY_SECRET")

    placeholders = (
        "replace_with_your_key_id",
        "replace_with_your_test_key_secret",
    )
    if any(value and placeholder in value.lower()
           for value in (RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET)
           for placeholder in placeholders):
        missing.append("replacement of example placeholder values")

    if RAZORPAY_KEY_ID and not RAZORPAY_KEY_ID.startswith("rzp_test_"):
        raise RuntimeError(
            "This demo is configured for Razorpay Test Mode only. "
            "Use a Key ID that starts with 'rzp_test_'; do not use live credentials."
        )

    if missing:
        names = " and ".join(missing)
        raise RuntimeError(
            f"Razorpay configuration is incomplete ({names}). Copy "
            "merchant-backend/.env.example to merchant-backend/.env and set "
            "the matching Razorpay Test Mode credentials."
        )


def get_config():
    """Return non-secret settings only."""
    return {
        "razorpay_key_configured": bool(RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET),
        "spend_cap": SPEND_CAP,
    }
