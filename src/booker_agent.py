"""Booking agent handles confirmation workflows."""

from datetime import date, timedelta
from typing import Optional, Dict, Any, List

from .tools import inventory_tools, booking_tools


class BookerError(Exception):
    """Custom exception for booking-related failures."""


def _split_nights_across_cities(cities: List[str], total_days: int) -> Dict[str, int]:
    """
    Evenly assign nights to each city, distributing any remainder to earlier cities.
    """
    if not cities:
        return {}
    base = total_days // len(cities)
    remainder = total_days % len(cities)
    nights = {}
    for idx, city in enumerate(cities):
        nights[city] = base + (1 if idx < remainder else 0)
    return nights


def book_itinerary(
    chosen_itinerary: Dict[str, Any],
    user_prefs: Dict[str, Any],
    payment_info: Optional[Dict[str, Any]],
    today: date,
) -> Dict[str, Any]:
    """
    Map a chosen itinerary to concrete flights and hotels, optionally executing a simulated booking.
    """
    try:
        origin_city = user_prefs["origin_city"]
        travel_style = user_prefs["travel_style"]
        budget_idr = user_prefs["budget_idr"]
        trip_length_days = user_prefs["trip_length_days"]
        start_date = date.fromisoformat(user_prefs["start_date"])
    except (KeyError, TypeError, ValueError) as exc:
        raise BookerError(f"Invalid user preferences: {exc}") from exc

    end_date = start_date + timedelta(days=trip_length_days - 1)

    cities = chosen_itinerary.get("cities") or []
    if not cities:
        raise BookerError("Chosen itinerary has no cities to visit.")

    first_city = cities[0]
    last_city = cities[-1]

    flights_result = inventory_tools.find_flights_for_trip(
        origin_city, first_city, last_city, start_date, end_date
    )
    outbound_options = flights_result.get("outbound_options", [])
    return_options = flights_result.get("return_options", [])
    if not outbound_options or not return_options:
        raise BookerError("No available outbound or return flights for the selected trip.")

    outbound = min(outbound_options, key=lambda f: int(f.get("base_price_idr", 0)))
    returning = min(return_options, key=lambda f: int(f.get("base_price_idr", 0)))
    chosen_flights = [outbound, returning]

    nights_per_city = _split_nights_across_cities(cities, trip_length_days)
    chosen_hotels: List[Dict[str, Any]] = []
    country = chosen_itinerary.get("destination_country")

    day_offset = 0
    for city in cities:
        nights = nights_per_city.get(city, 0)
        if nights <= 0:
            continue
        stay_start = start_date + timedelta(days=day_offset)
        stay_end = stay_start + timedelta(days=nights - 1)
        day_offset += nights

        candidates = inventory_tools.find_hotels_for_city(
            city, country, travel_style, stay_start, stay_end
        )
        if not candidates:
            fallback_style = None
            if travel_style == "luxury":
                fallback_style = "mid-range"
            elif travel_style == "mid-range":
                fallback_style = "backpacker"
            if fallback_style:
                candidates = inventory_tools.find_hotels_for_city(
                    city, country, fallback_style, stay_start, stay_end
                )
        if not candidates:
            raise BookerError(f"No hotels available in {city} for style {travel_style}.")

        hotel = min(candidates, key=lambda h: int(h.get("price_per_night_idr", 0)))
        hotel_copy = dict(hotel)
        hotel_copy["nights"] = nights
        hotel_copy["stay_start_date"] = stay_start.isoformat()
        hotel_copy["stay_end_date"] = stay_end.isoformat()
        chosen_hotels.append(hotel_copy)

    outbound_cost = int(outbound.get("base_price_idr", 0))
    return_cost = int(returning.get("base_price_idr", 0))
    total_flights = outbound_cost + return_cost
    total_accommodation = sum(
        int(h.get("price_per_night_idr", 0)) * int(h.get("nights", 0)) for h in chosen_hotels
    )
    base_cost = total_flights + total_accommodation
    extra = int(base_cost * 0.2)  # activities + local transport buffer
    total_price_idr = base_cost + extra
    budget_warning = total_price_idr > int(budget_idr * 1.2)

    stay_plan = [
        {
            "city": h.get("city"),
            "country": h.get("country"),
            "hotel_id": h.get("id"),
            "hotel_name": h.get("name"),
            "nights": h.get("nights"),
            "stay_start_date": h.get("stay_start_date"),
            "stay_end_date": h.get("stay_end_date"),
            "category": h.get("category"),
        }
        for h in chosen_hotels
    ]

    cost_breakdown = {
        "outbound_flight": outbound_cost,
        "return_flight": return_cost,
        "total_flights": total_flights,
        "accommodation": total_accommodation,
        "buffer_activities_transport": extra,
        "grand_total": total_price_idr,
    }

    if payment_info is not None and payment_info.get("auto_book_allowed") is True:
        payment_result = booking_tools.simulate_payment(total_price_idr, payment_info)
        booking_record = booking_tools.create_booking(
            country=country,
            cities=cities,
            start_date=start_date,
            end_date=end_date,
            flights=chosen_flights,
            hotels=chosen_hotels,
            total_price_idr=total_price_idr,
            payment_info=payment_info,
            payment_result=payment_result,
        )
        return {
            "status": "booked",
            "total_price_idr": total_price_idr,
            "budget_warning": budget_warning,
            "booking_record": booking_record,
            "stay_plan": stay_plan,
            "cost_breakdown": cost_breakdown,
        }

    return {
        "status": "simulation_only",
        "total_price_idr": total_price_idr,
        "budget_warning": budget_warning,
        "proposed_flights": chosen_flights,
        "proposed_hotels": chosen_hotels,
        "stay_plan": stay_plan,
        "cost_breakdown": cost_breakdown,
    }
