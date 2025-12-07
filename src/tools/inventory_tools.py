"""Inventory lookup tools for Smart Vacation Planner."""

import json
from pathlib import Path
from typing import List, Dict
from datetime import date

# TODO: Implement inventory queries against datasets.

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _load_json_list(filename: str) -> List[Dict]:
    """Utility to load a JSON list from data folder, returning [] on error."""
    dataset_path = DATA_DIR / filename
    try:
        with dataset_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, list):
            raise ValueError(f"{filename} root must be a list")
        return data
    except FileNotFoundError:
        # TODO: Replace with structured logging.
        return []
    except (json.JSONDecodeError, ValueError):
        return []


def load_countries_metadata() -> List[Dict]:
    """
    Load country and city metadata from the JSON dataset.

    Returns an empty list if the file is missing or invalid JSON.
    """
    return _load_json_list("countries.json")


def get_cities_for_country(country: str) -> List[Dict]:
    """
    Return metadata entries for the requested country.

    Matches on case-insensitive country name.
    """
    metadata = load_countries_metadata()
    normalized = country.strip().lower()
    return [
        entry
        for entry in metadata
        if str(entry.get("country", "")).strip().lower() == normalized
    ]


def _parse_date(value) -> date | None:
    """Parse ISO date string into a date object; return None on failure."""
    try:
        return date.fromisoformat(str(value))
    except Exception:
        return None


def load_flights() -> List[Dict]:
    """
    Load flight-like inventory data to support booking agent searches.

    Intended for outbound and return flight selection given user origin and destinations.
    """
    return _load_json_list("flights.json")


def load_hotels() -> List[Dict]:
    """
    Load hotel inventory data to support lodging selection per city and travel style.

    Intended for booking agent hotel matching after the planner chooses destinations.
    """
    return _load_json_list("hotels.json")


def find_flights_for_trip(
    origin: str,
    first_city: str,
    last_city: str,
    start_date: date,
    return_date: date,
) -> Dict[str, List[Dict]]:
    """
    Find outbound and return flight options with available seats on matching dates.

    Outbound: from origin -> first_city.
    Return: from last_city -> origin.
    """
    flights = load_flights()
    outbound_options = [
        f
        for f in flights
        if str(f.get("from", "")).lower() == origin.strip().lower()
        and str(f.get("to", "")).lower() == first_city.strip().lower()
        and int(f.get("seats_left", 0)) > 0
        and _parse_date(f.get("date")) == start_date
    ]
    return_options = [
        f
        for f in flights
        if str(f.get("from", "")).lower() == last_city.strip().lower()
        and str(f.get("to", "")).lower() == origin.strip().lower()
        and int(f.get("seats_left", 0)) > 0
        and _parse_date(f.get("date")) == return_date
    ]
    # Fallback to nearest-date options if exact dates missing.
    if not outbound_options:
        outbound_candidates = [
            f
            for f in flights
            if str(f.get("from", "")).lower() == origin.strip().lower()
            and str(f.get("to", "")).lower() == first_city.strip().lower()
            and int(f.get("seats_left", 0)) > 0
            and _parse_date(f.get("date")) is not None
        ]
        outbound_candidates.sort(
            key=lambda f: abs((_parse_date(f.get("date")) - start_date).days)
        )
        outbound_options = outbound_candidates[:5]
    if not return_options:
        return_candidates = [
            f
            for f in flights
            if str(f.get("from", "")).lower() == last_city.strip().lower()
            and str(f.get("to", "")).lower() == origin.strip().lower()
            and int(f.get("seats_left", 0)) > 0
            and _parse_date(f.get("date")) is not None
        ]
        return_candidates.sort(
            key=lambda f: abs((_parse_date(f.get("date")) - return_date).days)
        )
        return_options = return_candidates[:5]
    return {"outbound_options": outbound_options, "return_options": return_options}


def find_hotels_for_city(
    city: str,
    country: str,
    style: str,
    stay_start: date,
    stay_end: date,
) -> List[Dict]:
    """
    Find hotels in a city that match travel style, have remaining rooms, and cover the stay dates.

    Booking agent can call this after planner picks destinations and budget/style.
    """
    hotels = load_hotels()
    return [
        h
        for h in hotels
        if str(h.get("city", "")).lower() == city.strip().lower()
        and str(h.get("country", "")).lower() == country.strip().lower()
        and str(h.get("category", "")).lower() == style.strip().lower()
        and int(h.get("rooms_left", 0)) > 0
        and (af := _parse_date(h.get("available_from"))) is not None
        and (at := _parse_date(h.get("available_to"))) is not None
        and af <= stay_start <= at
        and af <= stay_end <= at
    ]


# Example quick checks (not executed by default):
# assert load_countries_metadata(), "Expected countries metadata to be non-empty."
# assert {c["city"] for c in get_cities_for_country("Japan")} >= {"Tokyo", "Kyoto", "Osaka"}
# assert find_flights_for_trip("Jakarta", "Bali", "Jakarta")["outbound_options"], "Should find outbound flights with seats."
# assert any(h["city"] == "Tokyo" for h in find_hotels_for_city("Tokyo", "Japan", "backpacker")), "Should return Tokyo hostels."


def get_available_flights(origin: str, destination: str):
    """Placeholder to fetch available flights."""
    # TODO: Return flight options from data store.
    return []


def get_available_hotels(destination: str):
    """Placeholder to fetch available hotels."""
    # TODO: Return hotel options from data store.
    return []
