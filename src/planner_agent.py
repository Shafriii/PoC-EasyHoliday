"""Planner agent orchestrates travel planning logic."""

import json
import re
from typing import List, Dict, Any

from .llm_client import call_llm, LLMError


class PlannerError(Exception):
    """Custom exception for planner-related failures."""


def generate_itineraries(
    user_prefs: Dict[str, Any],
    countries_metadata: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Generate up to 3 itinerary options using the LLM, constrained by provided city metadata.
    """
    destination_country = user_prefs.get("destination_country")
    normalized_dest = str(destination_country or "").strip().lower()
    relevant_cities = [
        entry
        for entry in countries_metadata
        if str(entry.get("country", "")).strip().lower() == normalized_dest
    ]

    if not relevant_cities:
        raise PlannerError(f"No destination data found for country: {destination_country}")

    allow_multi_city = len(relevant_cities) >= 3

    system_prompt = (
        "Reset context completely; ignore any previous conversation. "
        "You are a vacation itinerary planner. "
        "You may reason internally, but the final output MUST be ONLY valid JSON. "
        "Requirements: propose up to 3 itinerary options; use only the provided destination cities; "
        "if few cities, use one city as base; if many, you may use 2-3 cities; "
        "for each day create a detailed hourly schedule (e.g., '08:00', '10:30'); "
        "include concise notes in each slot so the user can imagine the experience; "
        "include an estimated_cost_idr per activity slot; "
        "when moving between cities, include realistic transport steps (e.g., depart Tokyo Station to Osaka Station, not teleport). "
        "Respect user budget and provide a budget breakdown; output must be a JSON array "
        "matching the required schema exactly. No extra commentary, explanations, or keys."
    )

    payload = {
        "user_prefs": user_prefs,
        "destination_cities_metadata": relevant_cities,
        "allow_multi_city": allow_multi_city,
    }

    schema_example = """
[
  {
    "option_id": "string",
    "title": "string",
    "destination_country": "string",
    "cities": ["city1", "city2"],
    "total_days": 0,
    "estimated_total_budget_idr": 0,
    "budget_breakdown": {
      "flights": 0,
      "accommodation": 0,
      "activities": 0,
      "local_transport": 0
    },
    "daily_schedule": [
      {
        "day_number": 1,
        "city": "string",
        "date_offset_from_start": 0,
        "slots": [
          {
            "time": "08:00",
            "place": "string",
            "activity": "string",
            "notes": "string",
            "estimated_cost_idr": 0
          }
        ]
      }
    ]
  }
]
""".strip()

    user_prompt = (
        "Given the payload below, return ONLY a JSON array of itineraries that fits the schema.\n\n"
        f"Payload:\n{json.dumps(payload, indent=2)}\n\n"
        "Required output schema example (match keys and structure):\n"
        f"{schema_example}\n\n"
        "Return ONLY this JSON array, nothing else."
    )

    try:
        raw_output = call_llm(system_prompt=system_prompt, user_prompt=user_prompt)
    except LLMError as exc:
        raise PlannerError(f"LLM call failed: {exc}") from exc

    text = raw_output.strip()
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1 or end < start:
        raise PlannerError(f"Could not locate JSON array in LLM response: {raw_output}")

    json_str = text[start : end + 1]
    try:
        itineraries = json.loads(json_str)
    except json.JSONDecodeError:
        # Attempt common sanitization fixes before failing.
        sanitized = (
            json_str.replace('""time"', '"time"')
            .replace('"date_offset_from"', '"date_offset_from_start"')
        )
        try:
            itineraries = json.loads(sanitized)
        except json.JSONDecodeError as exc:
            raise PlannerError(f"Failed to parse itineraries JSON: {exc}; raw: {json_str}") from exc

    if not isinstance(itineraries, list):
        raise PlannerError("Parsed itineraries payload is not a list.")

    return itineraries


class PlannerAgent:
    """Placeholder class wrapper that could later orchestrate planning with state."""

    def __init__(self) -> None:
        # TODO: Wire PlannerAgent to use generate_itineraries and other components.
        pass

    def plan_trip(self, request) -> dict:
        """Placeholder for trip planning workflow."""
        # TODO: Implement planning steps or delegate to generate_itineraries.
        return {}
