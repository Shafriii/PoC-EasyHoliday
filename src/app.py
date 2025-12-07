"""Entry point for the Smart Vacation Planner app."""

import json
import sys
import time
from pathlib import Path
from datetime import date, timedelta

import streamlit as st

# Support running as a script (e.g., `streamlit run src/app.py`).
if __package__ in (None, ""):
    sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.tools import payment_tools, inventory_tools, booking_tools
from src.planner_agent import generate_itineraries, PlannerError
from src.booker_agent import book_itinerary, BookerError


def load_bookings():
    """Load existing bookings for display."""
    return booking_tools.load_bookings()


def format_idr(value: int | float | None) -> str:
    """Format numbers as IDR currency style."""
    if value is None:
        return "-"
    try:
        return f"IDR {int(value):,}".replace(",", ".")
    except Exception:
        return str(value)


def main() -> None:
    """Run the Streamlit UI."""
    st.set_page_config(page_title="EasyHoliday-PoC", layout="wide")
    st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)
    st.title("EasyHoliday-PoC")
    st.caption("Plan, preview, and simulate bookings with a streamlined flow.")
    st.markdown(
        """
        <style>
        .block-container {max-width: 1100px; padding-top: 1rem; padding-bottom: 2rem;}
        h1, h2, h3, h4 {margin-bottom: 0.4rem;}
        .stRadio > label {font-weight: 600;}
        div[data-baseweb="select"] > div {min-height: 40px;}
        div[data-baseweb="slider"] {padding-top: 0.25rem; padding-bottom: 0.5rem;}
        .compact-table table {font-size: 0.9rem;}
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Sidebar: payment & permissions
    with st.sidebar.expander("Payment & Permissions (Simulated)", expanded=False):
        existing_payment = payment_tools.get_payment_info()
        if existing_payment and existing_payment.get("has_payment"):
            st.success(
                f"Payment on file: {existing_payment.get('card_brand')} ****{existing_payment.get('card_last4')} "
                f"(auto-book: {'yes' if existing_payment.get('auto_book_allowed') else 'no'})"
            )
        else:
            st.info("No payment method saved yet.")

        with st.form("payment_form"):
            card_number = st.text_input("Card number")
            expiry = st.text_input("Expiry (MM/YY)")
            cvv = st.text_input("CVV", type="password")
            auto_book_allowed = st.checkbox("Allow auto-booking", value=True)
            submit_payment = st.form_submit_button("Save payment (simulated)")
            if submit_payment:
                if not card_number or not expiry or not cvv:
                    st.error("Please fill all payment fields.")
                else:
                    saved = payment_tools.save_payment(card_number, expiry, cvv, auto_book_allowed)
                    st.success(
                        f"Saved payment ending ****{saved.get('card_last4')} "
                        f"(auto-book: {'yes' if saved.get('auto_book_allowed') else 'no'})"
                    )

    # Main: trip planner form
    st.header("Plan Your Trip")
    countries_metadata = inventory_tools.load_countries_metadata()
    all_countries = sorted({entry["country"] for entry in countries_metadata})

    if "itineraries" not in st.session_state:
        st.session_state["itineraries"] = None
    if "user_prefs" not in st.session_state:
        st.session_state["user_prefs"] = None
    if "start_date_input" not in st.session_state:
        st.session_state["start_date_input"] = date.today()
    if "trip_length_days_input" not in st.session_state:
        st.session_state["trip_length_days_input"] = 5
    if "end_date_input" not in st.session_state:
        st.session_state["end_date_input"] = st.session_state["start_date_input"] + timedelta(
            days=st.session_state["trip_length_days_input"] - 1
        )

    def _clamp_days(val: int) -> int:
        return max(2, min(14, int(val)))

    def _on_days_change():
        days_val = _clamp_days(st.session_state.get("trip_length_days_input", 5))
        st.session_state["trip_length_days_input"] = days_val
        start_d = st.session_state.get("start_date_input", date.today())
        st.session_state["end_date_input"] = start_d + timedelta(days=days_val - 1)

    def _on_start_change():
        days_val = _clamp_days(st.session_state.get("trip_length_days_input", 5))
        start_d = st.session_state.get("start_date_input", date.today())
        st.session_state["end_date_input"] = start_d + timedelta(days=days_val - 1)

    def _on_end_change():
        start_d = st.session_state.get("start_date_input", date.today())
        end_d = st.session_state.get("end_date_input", start_d)
        new_days = _clamp_days((end_d - start_d).days + 1)
        st.session_state["trip_length_days_input"] = new_days

    form_container = st.container()
    with form_container:
        row1_col1, row1_col2 = st.columns([1, 1])
        with row1_col1:
            origin_country = st.selectbox("Origin Country", all_countries) if all_countries else ""
            origin_cities = sorted(
                {entry["city"] for entry in countries_metadata if entry["country"] == origin_country}
            )
            origin_city = st.selectbox("Origin City", origin_cities) if origin_cities else ""
        with row1_col2:
            dest_options = [c for c in all_countries if c != origin_country] or all_countries
            destination_country = st.selectbox("Destination Country", dest_options) if dest_options else ""
            dest_cities = sorted(
                {entry["city"] for entry in countries_metadata if entry["country"] == destination_country}
            )
            if dest_cities:
                st.caption(f"Available cities for {destination_country}: {', '.join(dest_cities)}")

        row2_pref, row2_len = st.columns([2, 1])
        with row2_pref:
            prefs = st.multiselect(
                "Travel preferences (optional)",
                ["beach", "culture", "food", "nature", "shopping", "nightlife", "wellness"],
            )
        with row2_len:
            trip_length_days = st.slider(
                "Trip length (days)",
                min_value=2,
                max_value=14,
                key="trip_length_days_input",
                on_change=_on_days_change,
            )

        row3_col1, row3_col2, row3_col3 = st.columns([1, 1, 1])
        with row3_col1:
            start_date_input = st.date_input(
                "Start date", key="start_date_input", on_change=_on_start_change, format="DD/MM/YYYY"
            )
        with row3_col2:
            budget_idr = st.number_input(
                "Budget (IDR)", min_value=500_000, step=500_000, value=5_000_000, format="%i"
            )
        with row3_col3:
            travel_style = st.selectbox("Travel style", ["backpacker", "mid-range", "luxury"])
        end_col1, end_col2, end_col3 = st.columns([1, 1, 1])
        with end_col1:
            end_date_input = st.date_input(
                "End date", key="end_date_input", on_change=_on_end_change, format="DD/MM/YYYY"
            )
        action_col, _ = st.columns([1, 3])
        generate_clicked = action_col.button("Generate itineraries", use_container_width=True)

    if generate_clicked:
        user_prefs = {
            "origin_country": origin_country,
            "origin_city": origin_city,
            "destination_country": destination_country,
            "preferences": prefs,
            "trip_length_days": trip_length_days,
            "start_date": start_date_input.isoformat(),
            "budget_idr": int(budget_idr),
            "travel_style": travel_style,
        }
        start_time = time.perf_counter()
        with st.spinner("Generating itineraries..."):
            try:
                itineraries = generate_itineraries(user_prefs, countries_metadata)
                st.session_state["itineraries"] = itineraries
                st.session_state["user_prefs"] = user_prefs
                duration = time.perf_counter() - start_time
                st.success("Generated itineraries.")
                st.caption(f"LLM generation time: {duration:.1f} seconds")
            except PlannerError as exc:
                st.error(f"Failed to generate itineraries: {exc}")


    st.subheader("Itinerary Options")
    itineraries = st.session_state.get("itineraries")
    chosen_option_id = None
    option_ids = []
    option_map = {}
    if itineraries:
        option_ids = [opt.get("option_id", f"option-{idx+1}") for idx, opt in enumerate(itineraries)]
        option_map = {oid: opt for oid, opt in zip(option_ids, itineraries)}
        labels = [f"{oid} - {option_map[oid].get('title', 'Itinerary')}" for oid in option_ids]
        chosen_label = st.radio("Choose an itinerary to preview/book", options=labels)
        chosen_option_id = chosen_label.split(" - ")[0] if chosen_label else None

        if chosen_option_id and chosen_option_id in option_map:
            opt = option_map[chosen_option_id]
            st.markdown(f"### {chosen_option_id} - {opt.get('title', 'Itinerary')}")
            meta_col, budget_col = st.columns([2.2, 1])
            with meta_col:
                st.write(f"Destination Country: {opt.get('destination_country')}")
                st.write(f"Cities: {', '.join(opt.get('cities', []))}")
                st.write(f"Estimated Total Budget: {format_idr(opt.get('estimated_total_budget_idr'))}")
            with budget_col:
                st.write("Budget breakdown (IDR):")
                budget_data = opt.get("budget_breakdown", {}) or {}
                if budget_data:
                    st.table({k: [format_idr(v)] for k, v in budget_data.items()})
                else:
                    st.info("No budget breakdown provided.")
            daily_schedule = opt.get("daily_schedule", [])
            if chosen_option_id != st.session_state.get("last_option_id"):
                st.session_state["day_index"] = 0
                st.session_state["last_option_id"] = chosen_option_id
            day_index = st.session_state.get("day_index", 0)
            if daily_schedule:
                day_index = max(0, min(day_index, len(daily_schedule) - 1))
                st.session_state["day_index"] = day_index
                current_day = daily_schedule[day_index]
                st.markdown(
                    f"**Day {current_day.get('day_number')} of {len(daily_schedule)} - {current_day.get('city')}**"
                )
                slots = current_day.get("slots", [])
                if slots:
                    st.table(slots)
                nav_cols = st.columns([1, 1, 6])
                if nav_cols[0].button("Previous day", key=f"prev_{chosen_option_id}"):
                    st.session_state["day_index"] = (day_index - 1) % len(daily_schedule)
                if nav_cols[1].button("Next day", key=f"next_{chosen_option_id}"):
                    st.session_state["day_index"] = (day_index + 1) % len(daily_schedule)
    else:
        st.info("Generate itineraries to see options.")

    st.subheader("Book Selected Itinerary")
    if "pending_selection" not in st.session_state:
        st.session_state["pending_selection"] = None
    if "pending_result" not in st.session_state:
        st.session_state["pending_result"] = None

    step1_col, step2_col = st.columns([1, 1])
    trigger_preview = step1_col.button("Preview flights & hotels")

    if trigger_preview:
        if not itineraries or not chosen_option_id:
            st.error("Please generate and select an itinerary first.")
        else:
            chosen_itinerary = None
            for opt, opt_id in zip(itineraries, option_ids):
                if opt_id == chosen_option_id:
                    chosen_itinerary = opt
                    break
            if not chosen_itinerary:
                st.error("Could not find the selected itinerary.")
            else:
                st.session_state["pending_selection"] = chosen_itinerary
                st.session_state["pending_result"] = None

    pending = st.session_state.get("pending_selection")
    if pending:
        st.info("Previewing selection. Review flights, hotels, and costs before confirming.")
        payment_info_preview = payment_tools.get_payment_info()
        user_prefs_preview = st.session_state.get("user_prefs") or {}
        try:
            preview = book_itinerary(
                chosen_itinerary=pending,
                user_prefs=user_prefs_preview,
                payment_info=None,  # preview only
                today=date.today(),
            )
            st.write(f"Total price: {format_idr(preview.get('total_price_idr'))}")
            if preview.get("budget_warning"):
                st.warning("Total price may exceed your budget buffer (20% over).")
            if preview.get("cost_breakdown"):
                st.write("Cost breakdown:")
                st.table({k: [format_idr(v)] for k, v in preview.get("cost_breakdown", {}).items()})
            st.json({"proposed_flights": preview.get("proposed_flights", [])})
            st.json({"proposed_hotels": preview.get("proposed_hotels", [])})
            if preview.get("stay_plan"):
                st.write("Stay plan by city and dates:")
                st.table(preview.get("stay_plan"))
        except BookerError as exc:
            st.error(f"Preview failed: {exc}")
            st.session_state["pending_selection"] = None
            st.session_state["pending_result"] = None

        confirm_booking = step2_col.button("Confirm booking now")
        if confirm_booking:
            payment_info = payment_tools.get_payment_info()
            if not payment_info or not payment_info.get("auto_book_allowed"):
                st.error("No auto-book payment available. Save payment with auto-book to proceed.")
            else:
                try:
                    result = book_itinerary(
                        chosen_itinerary=pending,
                        user_prefs=user_prefs_preview,
                        payment_info=payment_info,
                        today=date.today(),
                    )
                    st.session_state["pending_result"] = result
                    st.session_state["pending_selection"] = None
                except BookerError as exc:
                    st.error(f"Booking failed: {exc}")

    if st.session_state.get("pending_result"):
        result = st.session_state["pending_result"]
        st.success("Trip booked (simulated)!")
        st.write(f"Status: {result.get('status')}")
        st.write(f"Total price: {format_idr(result.get('total_price_idr'))}")
        if result.get("budget_warning"):
            st.warning("Total price may exceed your budget buffer (20% over).")
        if result.get("cost_breakdown"):
            st.write("Cost breakdown:")
            st.table({k: [format_idr(v)] for k, v in result.get("cost_breakdown", {}).items()})
        st.json(result.get("booking_record", {}))

    st.subheader("Existing Bookings (Simulated)")
    try:
        bookings = load_bookings()
        if bookings:
            summary_rows = []
            for b in bookings:
                summary_rows.append(
                    {
                        "booking_id": b.get("booking_id"),
                        "country": b.get("country"),
                        "cities": ", ".join(b.get("cities", [])),
                        "start_date": b.get("start_date"),
                        "end_date": b.get("end_date"),
                        "flights": ", ".join(b.get("flight_ids", [])),
                        "hotels": ", ".join(b.get("hotel_ids", [])),
                        "total_price": format_idr(b.get("total_price_idr")),
                        "payment_txn": b.get("payment_transaction_id"),
                        "card_last4": b.get("card_last4"),
                    }
                )
            st.markdown('<div class="compact-table">', unsafe_allow_html=True)
            st.table(summary_rows)
            st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.info("No bookings yet.")
    except Exception as exc:  # noqa: BLE001
        st.error(f"Failed to load bookings: {exc}")


if __name__ == "__main__":
    main()
