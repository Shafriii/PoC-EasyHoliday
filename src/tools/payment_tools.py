"""Payment utilities for Smart Vacation Planner.

Simulates storing payment authorization details for the booking agent.
"""

from pathlib import Path
import json
import uuid
from typing import Dict, Optional

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
PAYMENTS_FILE = DATA_DIR / "payments.json"


def _write_json(path: Path, payload) -> None:
    """Write JSON to disk with basic error surfacing."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
    except OSError as exc:
        raise RuntimeError(f"Failed to write {path}: {exc}") from exc


def _read_json(path: Path, default):
    """Read JSON from disk returning a default on error."""
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        return default
    except json.JSONDecodeError:
        return default
    except OSError as exc:
        raise RuntimeError(f"Failed to read {path}: {exc}") from exc


def save_payment(card_number: str, expiry: str, cvv: str, auto_book_allowed: bool) -> Dict:
    """
    Store masked payment metadata for later booking use.

    Does not persist full card numbers; only keeps last4, brand guess, and a mock token.
    """
    digits_only = "".join(ch for ch in card_number if ch.isdigit())
    card_last4 = digits_only[-4:] if digits_only else "0000"

    # Simple brand inference; defaults to a mock brand.
    if digits_only.startswith("4"):
        card_brand = "Visa"
    elif digits_only.startswith(("51", "52", "53", "54", "55")):
        card_brand = "Mastercard"
    elif digits_only.startswith("34") or digits_only.startswith("37"):
        card_brand = "Amex"
    else:
        card_brand = "MockCard"

    payment_record = {
        "has_payment": True,
        "card_last4": card_last4,
        "card_brand": card_brand,
        "token_id": f"tok_demo_{uuid.uuid4().hex}",
        "auto_book_allowed": bool(auto_book_allowed),
    }

    _write_json(PAYMENTS_FILE, payment_record)
    return payment_record


def get_payment_info() -> Optional[Dict]:
    """
    Retrieve stored payment metadata if available.

    Returns None when no valid payment is stored.
    """
    data = _read_json(PAYMENTS_FILE, default={})
    if isinstance(data, dict) and data.get("has_payment") is True:
        return data
    return None


# Example quick checks (not executed by default):
# assert save_payment("4111111111111111", "12/29", "123", True)["card_last4"] == "1111"
# assert get_payment_info() is None or get_payment_info().get("has_payment") is True
