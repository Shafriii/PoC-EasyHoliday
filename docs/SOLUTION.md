# Solution Notes

## Architecture
- **App shell**: Streamlit UI (`src/app.py`) drives user inputs, itinerary generation, selection, and booking/simulation. Uses sidebar expander for payment state.
- **Agents**:
  - Planner (`src/planner_agent.py`): prompts the LLM via `call_llm`, enforcing JSON-only responses with daily schedules and per-activity cost estimates.
  - Booker (`src/booker_agent.py`): maps itineraries to concrete flights/hotels, computes budgets, and optionally simulates bookings with inventory updates.
- **LLM client** (`src/llm_client.py`): single entry for Ollama chat, model name centralized; streaming disabled; resilient JSON extraction with fallbacks.
- **Tools**:
  - Inventory (`src/tools/inventory_tools.py`): load/filter country, flight (dated), and hotel (date-windowed) data; date-aware flight/hotel lookup.
  - Booking (`src/tools/booking_tools.py`): simulate payment, persist bookings, decrement availability, return structured booking records with stays and flight details.
  - Payment (`src/tools/payment_tools.py`): store masked card info, generate mock tokens, return cached payment state.
- **Data**: JSON under `src/data/` for countries, flights, hotels, bookings, payments. Flights/hotels include dates and availability; countries enriched with themes/notes.

## Agent Design
- **Planner**:
  - Inputs: user prefs + destination metadata. Filters to destination cities; multi-city allowed if ≥3 cities.
  - Prompt: resets context; demands strict JSON array schema; realistic transport steps; per-slot notes and `estimated_cost_idr`.
  - Parsing: trims, strips `<think>`, extracts first/last JSON array; sanitizes common LLM glitches before failing with `PlannerError`.
- **Booker**:
  - Inputs: chosen itinerary, prefs, optional payment, today.
  - Flights: date-aware outbound/return search; cheapest available; nearest-date fallback.
  - Hotels: nights split per city; date-window and style filter with downgrade fallback; records stay windows.
  - Costs: outbound + return summed, accommodation, 20% buffer; budget warning if >120% of budget; returns cost breakdown and stay plan.
  - Booking: if auto-book allowed, simulate payment, persist booking, decrement inventory; else simulation proposal.

## Implementation Notes
- **LLM calls**: `stream=False`, no timeout; fallback JSON line parsing for NDJSON-like responses.
- **UI**:
  - Iteration: generate itineraries with spinner + elapsed time; radio selection updates preview without scrolling; day-by-day navigation via prev/next buttons; budget breakdown table pinned near meta info.
  - Booking: explicit “Confirm booking” checkbox gates payment use; shows stay plan, cost breakdown, and booking vs simulation outputs.
  - Payment: collapsible sidebar expander; masked storage only.
- **Data availability**: Flights cover all routes (and returns) daily through year-end; hotels provide rolling 30-day windows across all cities; availability stored in JSON for mutation during bookings.

## Next Steps
- Add tests for planner parsing, booking cost math, inventory date filters, and booking persistence.
- Improve LLM prompt guards (schema enforcement, max cities/days, tighter validation).
- Add caching for inventory loads and itinerary generation; paginate UI for large schedules.
- Introduce per-activity cost rollups and validation of `estimated_cost_idr` vs budget.

## Vulnerabilities & Risks
- **LLM output formatting drift (UI-driven inputs reduce injection risk)**  
  1) Even with UI-driven inputs (no free-form chat), the model can return malformed JSON or omit required fields.  
  2) Likelihood: medium; Impact: medium (bad UX, unusable itineraries), injection risk is low given structured inputs.  
  3) Mitigate with strict JSON parsing/sanitization, schema validation, bounding values, and concise prompts; keep rate limits/logging lightweight.  
  4) Monitor parse failures, schema-violation counts, and rejection rates; alert on spikes.
- **Unvalidated inventory mutations**  
  1) Malicious or buggy calls could write invalid JSON or negative availability.  
  2) Likelihood: low-medium; Impact: medium (corrupt data, booking errors).  
  3) Add input validation and clamps when decrementing; keep lightweight backups/versioned writes (cheap JSON snapshots).  
  4) Monitor write errors, JSON parse failures, and sudden availability drops; periodic integrity checks.
- **Payment info handling (even simulated)**  
  1) Accidental logging of full card numbers or leaking tokens in UI/logs.  
  2) Likelihood: low; Impact: medium-high (privacy).  
  3) Keep last4-only, avoid logging inputs, and mask in UI; no real processing so avoid storing anything beyond metadata.  
  4) Monitor logs for PAN-like patterns and verify files never contain full PAN.
- **Unauthorized booking actions**  
  1) Auto-booking triggered without explicit consent or stale payment state.  
  2) Likelihood: low; Impact: medium (unexpected bookings).  
  3) Require explicit checkbox, check `auto_book_allowed`, and reconfirm payment presence; cheap double-confirm step before write.  
  4) Monitor booking creations, especially when payment info absent; alert on anomalies.
- **Data freshness and date mismatches**  
  1) Outdated inventories or date-window bugs leading to impossible trips.  
  2) Likelihood: medium; Impact: medium (failed bookings, user frustration).  
  3) Validate date windows, include nearest-date fallback only with warnings; schedule periodic regeneration of inventories.  
  4) Track booking failure reasons and fallback usage rates.
