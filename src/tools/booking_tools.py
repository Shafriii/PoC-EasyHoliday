"""Booking helpers for Smart Vacation Planner.

Supports simulated payments and booking persistence for the PoC.
"""

from pathlib import Path
from datetime import datetime, date
import json
import uuid
from typing import List, Dict, Optional

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
BOOKINGS_FILE = DATA_DIR / "bookings.json"
FLIGHTS_FILE = DATA_DIR / "flights.json"
HOTELS_FILE = DATA_DIR / "hotels.json"


def _write_json(path: Path, payload) -> None:
    """Write JSON to disk with explicit error reporting."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
    except OSError as exc:
        raise RuntimeError(f"Failed to write {path}: {exc}") from exc


def _read_json(path: Path, default, expected_type=None):
    """Read JSON from disk, returning default when missing or invalid."""
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        if expected_type and not isinstance(data, expected_type):
            return default
        return data
    except FileNotFoundError:
        return default
    except json.JSONDecodeError:
        return default
    except OSError as exc:
        raise RuntimeError(f"Failed to read {path}: {exc}") from exc


def _isoformat_safe(value) -> str:
    """Best-effort ISO formatting for date/datetime inputs."""
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def load_bookings() -> List[Dict]:
    """Load persisted bookings for display or debugging."""
    return _read_json(BOOKINGS_FILE, default=[], expected_type=list)


def simulate_payment(total_price_idr: int, payment_info: Dict) -> Dict:
    """
    Simulate a payment transaction (always succeeds for this PoC).

    Booking agent can call this after choosing flights/hotels and totals.
    """
    return {
        "status": "success",
        "transaction_id": f"pay_{uuid.uuid4().hex}",
        "charged_amount_idr": total_price_idr,
        "card_last4": payment_info.get("card_last4"),
    }


def _decrement_inventory(path: Path, ids: List[str], quantity_field: str) -> None:
    """Decrement availability for matching inventory records."""
    if not ids:
        return
    data = _read_json(path, default=[], expected_type=list)
    ids_set = {str(i) for i in ids}
    changed = False
    for record in data:
        record_id = str(record.get("id", ""))
        if record_id in ids_set:
            remaining = int(record.get(quantity_field, 0))
            record[quantity_field] = max(0, remaining - 1)
            changed = True
    if changed:
        _write_json(path, data)


def create_booking(
    country: str,
    cities: List[str],
    start_date: date,
    end_date: date,
    flights: List[Dict],
    hotels: List[Dict],
    total_price_idr: int,
    payment_info: Dict,
    payment_result: Dict,
) -> Dict:
    """
    Persist a booking record and update inventory availability.

    Booking agent can call this after flights/hotels are selected and a payment
    token is available.
    """
    bookings = load_bookings()
    booking_id = f"BK-{len(bookings) + 1:04d}"
    created_at = datetime.utcnow().isoformat()

    flight_ids = [f.get("id") for f in flights if f.get("id")]
    hotel_ids = [h.get("id") for h in hotels if h.get("id")]

    stays = [
        {
            "hotel_id": h.get("id"),
            "hotel_name": h.get("name"),
            "city": h.get("city"),
            "country": h.get("country"),
            "nights": h.get("nights"),
            "stay_start_date": h.get("stay_start_date"),
            "stay_end_date": h.get("stay_end_date"),
            "category": h.get("category"),
            "price_per_night_idr": h.get("price_per_night_idr"),
        }
        for h in hotels
    ]

    record = {
        "booking_id": booking_id,
        "created_at": created_at,
        "country": country,
        "cities": list(cities),
        "start_date": _isoformat_safe(start_date),
        "end_date": _isoformat_safe(end_date),
        "flight_ids": flight_ids,
        "hotel_ids": hotel_ids,
        "stays": stays,
        "flight_details": flights,
        "total_price_idr": int(total_price_idr),
        "payment_transaction_id": payment_result.get("transaction_id"),
        "card_last4": payment_info.get("card_last4"),
    }

    bookings.append(record)
    _write_json(BOOKINGS_FILE, bookings)

    _decrement_inventory(FLIGHTS_FILE, flight_ids, "seats_left")
    _decrement_inventory(HOTELS_FILE, hotel_ids, "rooms_left")

    return record


# Example quick checks (not executed by default):
# fake_payment = {"card_last4": "1111"}
# pr = simulate_payment(1500000, fake_payment)
# create_booking("Japan", ["Tokyo"], date.today(), date.today(), [], [], 1500000, fake_payment, pr)
