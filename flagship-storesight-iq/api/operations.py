"""
Real-time Operations API endpoints.

Provides streaming operations data for Store Manager:
- Live sales by channel (in-store, delivery, app, third-party)
- Current staffing status
- Real-time transaction feed
- Alerts (weather, events, inventory)

Data flows from Lakebase streaming tables.
"""

from typing import List, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from config.settings import Settings, get_settings
from config.database import query_sql
from services.external_apis import weather_service, events_service
from config.domain import domain
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


def _store_location(store: dict) -> str:
    """Human 'City, ST' label from a store dict. Uses the store's ACTUAL state
    (carried from domain.json) — never a hardcoded region — so it's correct for
    any customer's geography. Omits blank parts gracefully."""
    parts = [str(store.get("city", "")).strip(), str(store.get("state", "")).strip()]
    return ", ".join(p for p in parts if p) or "Unknown"


def get_client_adjusted_time(request: Request) -> datetime:
    """Get current time adjusted to client's local timezone using X-Client-Local-Hour header."""
    server_now = datetime.now()
    server_hour = server_now.hour
    
    client_hour = None
    header_value = request.headers.get("X-Client-Local-Hour") if request else None
    if header_value:
        try:
            client_hour = int(header_value)
        except ValueError:
            pass
    
    if client_hour is not None:
        hour_offset = client_hour - server_hour
        return server_now + timedelta(hours=hour_offset)
    
    return server_now


# === Pydantic Models ===

class ChannelSales(BaseModel):
    """Sales breakdown by channel."""
    channel: str  # "in_store", "delivery", "app", "third_party"
    sales: float
    transactions: int
    percentage: float


class HourlySales(BaseModel):
    """Hourly sales data point."""
    hour: int
    sales: float
    transactions: int
    vs_forecast: float


class Transaction(BaseModel):
    """Single POS transaction."""
    txn_id: str
    timestamp: str
    items: List[str]
    total: float
    channel: str
    payment_method: str


class StaffStatus(BaseModel):
    """Current staffing status."""
    on_duty: int
    scheduled: int
    next_shift_time: str
    next_shift_employee: str


class Alert(BaseModel):
    """Operations alert."""
    id: str
    type: str  # "weather", "event", "inventory", "labor"
    severity: str  # "info", "warning", "critical"
    title: str
    message: str
    timestamp: str


class OperationsSummary(BaseModel):
    """Real-time operations summary."""
    store_id: int
    sales_today: float
    forecast_sales: float  # Used by frontend to recalculate vs_forecast when incremental txns added
    vs_yesterday_pct: float
    vs_forecast_pct: float
    current_hour_sales: float
    transactions_today: int
    channels: List[ChannelSales]
    staff: StaffStatus
    last_updated: str


# === Demo Data Generator ===

def get_shift_info_for_hour(current_hour: int, client_now: datetime) -> StaffStatus:
    """
    Calculate staffing based on the same shift structure used in Labor page.
    This ensures consistency between Operations and Labor views.
    
    Shift structure (matches api/labor.py):
    - Morning shift: 6 AM - 2 PM (3 employees)
    - Mid shift: 10 AM - 6 PM (2 employees)
    - Evening shift: 2 PM - 10 PM (3 employees)
    """
    # Same employee list as Labor page (api/labor.py DEMO_EMPLOYEES)
    employees = [
        {"id": 1, "name": "Maria Garcia", "role": "shift_lead"},
        {"id": 2, "name": "John Davis", "role": "prep_cook"},
        {"id": 3, "name": "Sarah Kim", "role": "prep_cook"},
        {"id": 4, "name": "Mike Rodriguez", "role": "prep_cook"},
        {"id": 5, "name": "Emily Chen", "role": "cashier"},
        {"id": 6, "name": "David Park", "role": "prep_cook"},
        {"id": 7, "name": "Jessica Lee", "role": "shift_lead"},
        {"id": 8, "name": "Chris Brown", "role": "prep_cook"},
    ]
    
    # Consistent shift assignments using seeded selection based on date
    import random
    date_seed = int(client_now.strftime("%Y%m%d"))
    rng = random.Random(date_seed)  # Seeded random for consistency within same day
    
    shuffled = employees.copy()
    rng.shuffle(shuffled)
    
    # Assign to shifts (same pattern as Labor page)
    morning_staff = shuffled[0:3]   # 6 AM - 2 PM
    mid_staff = shuffled[3:5]       # 10 AM - 6 PM
    evening_staff = shuffled[5:8]   # 2 PM - 10 PM
    
    # Calculate who's currently on duty based on hour
    on_duty_count = 0
    on_duty_employees = []
    
    if 6 <= current_hour < 14:
        # Morning shift is active
        on_duty_employees.extend(morning_staff)
    if 10 <= current_hour < 18:
        # Mid shift is active
        on_duty_employees.extend(mid_staff)
    if 14 <= current_hour < 22:
        # Evening shift is active
        on_duty_employees.extend(evening_staff)
    
    # Remove duplicates (shouldn't be any, but just in case)
    seen_ids = set()
    unique_on_duty = []
    for emp in on_duty_employees:
        if emp["id"] not in seen_ids:
            unique_on_duty.append(emp)
            seen_ids.add(emp["id"])
    
    on_duty_count = len(unique_on_duty)
    
    # Calculate total scheduled for the day
    total_scheduled = len(morning_staff) + len(mid_staff) + len(evening_staff)  # 8
    
    # Determine next shift
    next_shift_time = ""
    next_shift_employee = ""
    
    if current_hour < 6:
        # Before store opens - morning shift is next
        next_shift_time = "06:00 AM"
        next_shift_employee = morning_staff[0]["name"].split()[0] + " " + morning_staff[0]["name"].split()[1][0] + "."
    elif current_hour < 10:
        # Morning active, mid shift coming next
        next_shift_time = "10:00 AM"
        next_shift_employee = mid_staff[0]["name"].split()[0] + " " + mid_staff[0]["name"].split()[1][0] + "."
    elif current_hour < 14:
        # Morning + mid active, evening shift coming next
        next_shift_time = "02:00 PM"
        next_shift_employee = evening_staff[0]["name"].split()[0] + " " + evening_staff[0]["name"].split()[1][0] + "."
    elif current_hour < 18:
        # Mid and evening active, no more shifts today
        next_shift_time = "Tomorrow 06:00 AM"
        next_shift_employee = morning_staff[0]["name"].split()[0] + " " + morning_staff[0]["name"].split()[1][0] + "."
    elif current_hour < 22:
        # Only evening shift active
        next_shift_time = "Tomorrow 06:00 AM"
        next_shift_employee = morning_staff[0]["name"].split()[0] + " " + morning_staff[0]["name"].split()[1][0] + "."
    else:
        # After store closes
        next_shift_time = "Tomorrow 06:00 AM"
        next_shift_employee = morning_staff[0]["name"].split()[0] + " " + morning_staff[0]["name"].split()[1][0] + "."
    
    return StaffStatus(
        on_duty=on_duty_count,
        scheduled=total_scheduled,
        next_shift_time=next_shift_time,
        next_shift_employee=next_shift_employee
    )


def generate_demo_operations(store_id: int, local_hour: Optional[int] = None, client_now: Optional[datetime] = None) -> OperationsSummary:
    """Generate realistic demo operations data.
    
    Uses shared demo_data service for consistent sales/forecast numbers
    across Operations, Forecast, and other views.
    
    Args:
        store_id: Store identifier
        local_hour: User's local hour (0-23) from browser. If None, uses server time.
        client_now: Client's adjusted datetime. If None, uses server time.
    """
    from services.demo_data import demo_data
    
    # Use client's adjusted time if provided, otherwise server time
    now = client_now if client_now is not None else datetime.now()
    # Use user's local hour if provided, otherwise fall back to server time
    hour = local_hour if local_hour is not None else now.hour
    date_str = now.strftime("%Y-%m-%d")
    
    # Get consistent sales data from shared service
    sales_data = demo_data.get_sales_up_to_hour(store_id, date_str, hour)
    
    # Build channel breakdown from consistent percentages
    channel_breakdown = sales_data["channel_breakdown"]
    sales_today = sales_data["sales_today"]
    transactions_today = sales_data["transactions_today"]
    
    channels = [
        ChannelSales(
            channel="in_store",
            sales=round(sales_today * channel_breakdown["in_store"], 2),
            transactions=int(transactions_today * channel_breakdown["in_store"]),
            percentage=round(channel_breakdown["in_store"] * 100, 1)
        ),
        ChannelSales(
            channel="delivery",
            sales=round(sales_today * channel_breakdown["delivery"], 2),
            transactions=int(transactions_today * channel_breakdown["delivery"]),
            percentage=round(channel_breakdown["delivery"] * 100, 1)
        ),
        ChannelSales(
            channel="app",
            sales=round(sales_today * channel_breakdown["app"], 2),
            transactions=int(transactions_today * channel_breakdown["app"]),
            percentage=round(channel_breakdown["app"] * 100, 1)
        ),
        ChannelSales(
            channel="third_party",
            sales=round(sales_today * channel_breakdown["third_party"], 2),
            transactions=int(transactions_today * channel_breakdown["third_party"]),
            percentage=round(channel_breakdown["third_party"] * 100, 1)
        ),
    ]

    # Get staffing from shared logic (consistent with Labor page)
    staff_status = get_shift_info_for_hour(hour, now)

    return OperationsSummary(
        store_id=store_id,
        sales_today=sales_data["sales_today"],
        forecast_sales=sales_data["forecast_sales"],  # Used by frontend for vs_forecast recalc
        vs_yesterday_pct=sales_data["vs_yesterday_pct"],
        vs_forecast_pct=sales_data["vs_forecast_pct"],
        current_hour_sales=round(sales_data["current_hour_sales"], 2),
        transactions_today=sales_data["transactions_today"],
        channels=channels,
        staff=staff_status,
        last_updated=now.isoformat()
    )


# === Endpoints ===

@router.get("/summary/{store_id}")
async def get_operations_summary(
    request: Request,
    store_id: int,
    local_hour: Optional[int] = Query(None, description="User's local hour (0-23) for time-aware data"),
    settings: Settings = Depends(get_settings),
) -> OperationsSummary:
    """
    Get real-time operations summary for a store.
    
    Returns current sales, channel breakdown, staffing status.
    Currently uses simulated demo data.
    
    Args:
        local_hour: User's local hour from browser (query param or X-Client-Local-Hour header)
    """
    # Get client's adjusted time
    client_now = get_client_adjusted_time(request)
    
    # Try to get local_hour from header if not in query params
    effective_local_hour = local_hour
    if effective_local_hour is None:
        header_value = request.headers.get("X-Client-Local-Hour")
        if header_value:
            try:
                effective_local_hour = int(header_value)
            except ValueError:
                pass
    
    logger.info(f"Operations summary - query_local_hour={local_hour}, header_local_hour={request.headers.get('X-Client-Local-Hour')}, effective={effective_local_hour}")
    
    # Return simulated demo data using user's local hour and adjusted time
    return generate_demo_operations(store_id, local_hour=effective_local_hour, client_now=client_now)


@router.get("/hourly/{store_id}")
async def get_hourly_sales(
    request: Request,
    store_id: int,
    date: Optional[str] = Query(None, description="Date in YYYY-MM-DD format"),
    local_hour: Optional[int] = Query(None, description="User's local hour (0-23) for time-aware data"),
    settings: Settings = Depends(get_settings),
) -> List[HourlySales]:
    """
    Get hourly sales breakdown for a store.
    
    Returns sales by hour for charting.
    
    Args:
        local_hour: User's local hour from browser (query param or X-Client-Local-Hour header)
    """
    import random
    
    target_date = date or datetime.now().strftime("%Y-%m-%d")
    server_hour = datetime.now().hour
    
    # Try to get local_hour from header if not in query params
    effective_local_hour = local_hour
    if effective_local_hour is None:
        header_value = request.headers.get("X-Client-Local-Hour")
        if header_value:
            try:
                effective_local_hour = int(header_value)
            except ValueError:
                pass
    
    # Use user's local hour if provided, otherwise fall back to server time
    current_hour = effective_local_hour if effective_local_hour is not None else server_hour
    
    logger.info(f"Hourly sales request - server_hour={server_hour}, header={request.headers.get('X-Client-Local-Hour')}, effective_local_hour={effective_local_hour}, using current_hour={current_hour}")
    
    if date is not None:
        current_hour = 23  # Show full day for specific dates
    
    # Store hours: 6am to 10pm
    STORE_OPEN = 6
    STORE_CLOSE = 22
    
    # If it's before store opens (e.g., midnight-6am), show yesterday's full day
    # This ensures the chart always has data to display
    show_full_day = (date is not None) or (current_hour < STORE_OPEN)

    hourly_data = []
    for hour in range(STORE_OPEN, STORE_CLOSE):
        # Simulate daypart patterns
        if 11 <= hour < 14:  # Lunch
            base = random.uniform(300, 500)
        elif 17 <= hour < 20:  # Dinner
            base = random.uniform(200, 350)
        elif 6 <= hour < 10:  # Breakfast
            base = random.uniform(100, 200)
        else:
            base = random.uniform(50, 150)

        # Only include hours up to current if today and store is open
        if not show_full_day and hour > current_hour:
            continue

        hourly_data.append(HourlySales(
            hour=hour,
            sales=base,
            transactions=int(base / 12),
            vs_forecast=random.uniform(-15, 20)
        ))

    return hourly_data


def _generate_transaction_for_index(store_id: int, date_str: str, txn_index: int, txn_time: datetime) -> Transaction:
    """
    Generate a deterministic transaction based on store_id, date, and index.
    Same inputs will always produce the same transaction.
    """
    import random
    
    # Customer menu names come from the taxonomy (domain.yaml -> menu_items),
    # falling back to the prep subtype labels.
    menu_items = domain.menu_items() or [s["label"] for s in domain.prep_subtypes()]

    channels = ["in_store", "delivery", "app", "third_party"]
    payment_methods = ["credit", "debit", "cash", "apple_pay", "google_pay"]

    # Seed random for this specific transaction
    seed = hash(f"txn_{store_id}_{date_str}_{txn_index}") % (2**32)
    rng = random.Random(seed)

    # Generate deterministic transaction (prep-level ticket)
    num_items = rng.randint(1, 3)
    items = rng.sample(menu_items, num_items)
    total = sum(rng.uniform(11.99, 18.99) for _ in items)
    total += rng.choice([0, 2.99, 3.49])  # dipping sauces / drink add-on
    
    # Generate deterministic txn_id from the seed
    txn_id = f"{seed % 100000000:08x}"[:8]
    
    return Transaction(
        txn_id=txn_id,
        timestamp=txn_time.strftime("%I:%M %p"),
        items=items,
        total=round(total, 2),
        channel=rng.choice(channels),
        payment_method=rng.choice(payment_methods)
    )


@router.get("/transactions/{store_id}")
async def get_recent_transactions(
    request: Request,
    store_id: int,
    limit: int = Query(10, le=50),
    initial: bool = Query(False, description="If true, returns full initial batch; if false, returns only 1-2 new transactions"),
    start_index: int = Query(0, description="Starting index for streaming updates (used for deterministic generation)"),
    settings: Settings = Depends(get_settings),
) -> List[Transaction]:
    """
    Get recent transactions for live feed display.
    
    - initial=true: Returns full batch of transactions with staggered timestamps (for initial load)
    - initial=false: Returns 1-2 new transactions based on start_index (for streaming updates)
    
    Transactions are DETERMINISTIC for each store+date+index combo.
    Uses X-Client-Local-Hour header to generate timestamps in user's local time.
    """
    import random

    # Get client's local hour from header to generate appropriate timestamps
    server_now = datetime.now()
    server_hour = server_now.hour
    
    client_local_hour = None
    header_value = request.headers.get("X-Client-Local-Hour")
    if header_value:
        try:
            client_local_hour = int(header_value)
        except ValueError:
            pass
    
    # Calculate hour offset between server and client
    if client_local_hour is not None:
        hour_offset = client_local_hour - server_hour
    else:
        hour_offset = 0
    
    # Adjust server time to client's local time
    client_now = server_now + timedelta(hours=hour_offset)
    date_str = client_now.strftime("%Y-%m-%d")
    
    logger.debug(f"Transactions request - store={store_id}, date={date_str}, initial={initial}, start_index={start_index}")

    transactions = []
    
    if initial:
        # Initial load: return full batch with staggered timestamps
        # Use seeded random for the minute offsets to be consistent
        seed = hash(f"txn_times_{store_id}_{date_str}") % (2**32)
        time_rng = random.Random(seed)
        
        for i in range(limit):
            # Deterministic time offset
            minute_offset = i * 5 + time_rng.randint(0, 4)
            txn_time = client_now - timedelta(minutes=minute_offset)
            
            # Generate deterministic transaction
            txn = _generate_transaction_for_index(store_id, date_str, i, txn_time)
            transactions.append(txn)
    else:
        # Streaming update: return 1-2 new transactions based on start_index
        # The number of new transactions is also deterministic
        seed = hash(f"txn_count_{store_id}_{date_str}_{start_index}") % (2**32)
        count_rng = random.Random(seed)
        num_new = count_rng.randint(1, 2)
        
        for i in range(num_new):
            txn_index = start_index + i
            # Slight time offset for multiple transactions
            txn_time = client_now - timedelta(seconds=i * 10)
            
            txn = _generate_transaction_for_index(store_id, date_str, txn_index, txn_time)
            transactions.append(txn)

    return transactions


@router.get("/alerts/{store_id}")
async def get_operations_alerts(
    store_id: int,
    settings: Settings = Depends(get_settings),
) -> List[Alert]:
    """
    Get current alerts for a store.
    
    Includes weather impacts, local events, inventory warnings.
    Always shows current weather with sales/traffic impact predictions.
    """
    from services.demo_data import demo_data
    DEMO_STORES = demo_data.DEMO_STORES
    import uuid
    
    alerts = []
    now = datetime.now()
    
    # Find store location
    store = next((s for s in DEMO_STORES if s["store_id"] == store_id), DEMO_STORES[0])
    
    # ALWAYS show weather alert with smart messaging
    try:
        weather = await weather_service.get_current_weather(store["lat"], store["lng"])
        temp = weather.get("temperature", 70)
        condition = weather.get("condition", "clear")
        
        # Generate smart weather-based sales insight
        if temp > 90:
            severity = "warning"
            title = f"🌡️ Heat Wave: {temp:.0f}°F"
            message = "Hot weather ahead! Expect +25% cold drink attach and more delivery vs carryout. Stock extra 2-liters and ice."
        elif temp > 80:
            severity = "info"
            title = f"☀️ Warm Weather: {temp:.0f}°F"
            message = "Warm day expected. Push cold drink bundles and delivery deals; carryout may dip slightly."
        elif temp < 45:
            severity = "info"
            title = f"❄️ Cold Weather: {temp:.0f}°F"
            message = f"Chilly day! Expect +25% delivery orders. Pre-prep extra {domain.prep().get('item_noun_plural', 'prep batches')}."
        elif temp < 55:
            severity = "info"
            title = f"🧥 Cool Weather: {temp:.0f}°F"
            message = "Cool temperatures. Delivery demand up; stage extra drivers and hot bags."
        elif condition in ["rain", "heavy_rain", "rain_showers", "heavy_rain_showers"]:
            severity = "warning"
            title = f"🌧️ Rainy: {temp:.0f}°F"
            message = "Rain expected! Carryout traffic -20%, delivery orders +35%. Add drivers and check hot-bag inventory."
        elif condition in ["thunderstorm"]:
            severity = "warning"
            title = f"⛈️ Thunderstorm: {temp:.0f}°F"
            message = "Severe weather alert! Delivery spikes but drive times increase. Prioritize app orders and quote longer ETAs."
        elif condition in ["drizzle"]:
            severity = "info"
            title = f"🌦️ Light Rain: {temp:.0f}°F"
            message = "Light drizzle today. Slight increase in delivery orders expected."
        elif condition in ["snow", "heavy_snow"]:
            severity = "warning"
            title = f"🌨️ Snowy: {temp:.0f}°F"
            message = "Snow conditions! Delivery demand high but road times slow. Stagger promises and add drivers."
        elif condition in ["foggy"]:
            severity = "info"
            title = f"🌫️ Foggy: {temp:.0f}°F"
            message = "Foggy conditions. Normal operations expected, allow extra delivery drive time."
        else:
            # Clear/nice weather
            severity = "info"
            title = f"☀️ Pleasant: {temp:.0f}°F"
            message = f"Great weather! Expect a strong dinner rush and steady carryout. Keep {domain.prep().get('item_noun_plural', 'prep batches')} well-stocked."
        
        alerts.append(Alert(
            id=str(uuid.uuid4())[:8],
            type="weather",
            severity=severity,
            title=title,
            message=message,
            timestamp=now.isoformat()
        ))
    except Exception as e:
        # Fallback weather alert
        alerts.append(Alert(
            id=str(uuid.uuid4())[:8],
            type="weather",
            severity="info",
            title="🌤️ Weather Data",
            message="Weather data temporarily unavailable. Check local forecast for planning.",
            timestamp=now.isoformat()
        ))

    # Get local events (50 mile radius, next 7 days)
    try:
        events_impact = await events_service.check_event_impact(
            store["lat"], store["lng"]  # No date filter - get all upcoming events
        )
        
        if events_impact.get("has_any_events"):
            event_count = events_impact["event_count"]
            sports_count = events_impact.get("sports_count", 0)
            music_count = events_impact.get("music_count", 0)
            
            # Get first few event names
            event_names = [e["name"][:30] for e in events_impact["events"][:3]]
            
            if sports_count > 0:
                severity = "warning"
                title = f"🏟️ {event_count} Events This Week"
                message = f"Sports events nearby including: {', '.join(event_names)}. Expect +25% traffic on game days."
            elif music_count > 0:
                severity = "info"
                title = f"🎵 {event_count} Events This Week"
                message = f"Concerts/shows: {', '.join(event_names)}. Evening traffic boost expected."
            else:
                severity = "info"
                title = f"📅 {event_count} Local Events"
                message = f"Upcoming: {', '.join(event_names)}. Plan for increased regional traffic."
            
            alerts.append(Alert(
                id=str(uuid.uuid4())[:8],
                type="event",
                severity=severity,
                title=title,
                message=message,
                timestamp=now.isoformat()
            ))
        else:
            # No events - still show this info
            alerts.append(Alert(
                id=str(uuid.uuid4())[:8],
                type="event",
                severity="info",
                title="📅 No Major Events",
                message="No major events within 50 miles this week. Expect normal traffic patterns.",
                timestamp=now.isoformat()
            ))
    except Exception as e:
        alerts.append(Alert(
            id=str(uuid.uuid4())[:8],
            type="event",
            severity="info",
            title="📅 Events Data",
            message="Event data temporarily unavailable.",
            timestamp=now.isoformat()
        ))

    # Demo inventory alert (random but realistic)
    import random
    if random.random() > 0.5:
        _names = [ing["name"] for ing in domain.ingredients()[:4]] or ["Inventory item"]
        _windows = ["2 days", "1.5 days", "4 hours", "1 day"]
        low_items = random.choice(list(zip(_names, _windows)))
        alerts.append(Alert(
            id=str(uuid.uuid4())[:8],
            type="inventory",
            severity="warning",
            title="📦 Low Stock Alert",
            message=f"{low_items[0]} at {low_items[1]} supply - reorder recommended",
            timestamp=now.isoformat()
        ))

    return alerts


@router.get("/weather/{store_id}")
async def get_current_weather(
    store_id: int,
    settings: Settings = Depends(get_settings),
) -> dict:
    """
    Get current weather data for a store location.
    
    Returns detailed weather info for display in weather card.
    """
    from services.demo_data import demo_data
    DEMO_STORES = demo_data.DEMO_STORES
    
    # Find store location
    store = next((s for s in DEMO_STORES if s["store_id"] == store_id), DEMO_STORES[0])
    
    try:
        weather = await weather_service.get_current_weather(store["lat"], store["lng"])
        temp = weather.get("temperature", 70)
        condition = weather.get("condition", "clear")
        wind_speed = weather.get("wind_speed", 0)
        
        # Map condition to display info
        condition_display = {
            "clear": {"label": "Clear", "icon": "☀️", "color": "yellow"},
            "mainly_clear": {"label": "Mostly Clear", "icon": "🌤️", "color": "yellow"},
            "partly_cloudy": {"label": "Partly Cloudy", "icon": "⛅", "color": "gray"},
            "overcast": {"label": "Overcast", "icon": "☁️", "color": "gray"},
            "foggy": {"label": "Foggy", "icon": "🌫️", "color": "gray"},
            "drizzle": {"label": "Drizzle", "icon": "🌦️", "color": "blue"},
            "rain": {"label": "Rain", "icon": "🌧️", "color": "blue"},
            "heavy_rain": {"label": "Heavy Rain", "icon": "🌧️", "color": "blue"},
            "rain_showers": {"label": "Rain Showers", "icon": "🌦️", "color": "blue"},
            "heavy_rain_showers": {"label": "Heavy Showers", "icon": "🌧️", "color": "blue"},
            "snow": {"label": "Snow", "icon": "🌨️", "color": "blue"},
            "heavy_snow": {"label": "Heavy Snow", "icon": "❄️", "color": "blue"},
            "thunderstorm": {"label": "Thunderstorm", "icon": "⛈️", "color": "purple"},
        }.get(condition, {"label": condition.replace("_", " ").title(), "icon": "🌤️", "color": "gray"})
        
        # Generate sales impact prediction
        if temp > 90:
            impact = {"trend": "up", "message": "+25% cold drink attach", "severity": "high"}
        elif temp > 80:
            impact = {"trend": "up", "message": "+10% delivery mix", "severity": "medium"}
        elif temp < 45:
            impact = {"trend": "up", "message": "+25% delivery orders", "severity": "high"}
        elif temp < 55:
            impact = {"trend": "up", "message": "+15% delivery", "severity": "medium"}
        elif condition in ["rain", "heavy_rain", "thunderstorm", "rain_showers", "heavy_rain_showers"]:
            impact = {"trend": "mixed", "message": "-20% carryout, +35% delivery", "severity": "high"}
        elif condition in ["drizzle"]:
            impact = {"trend": "mixed", "message": "+10% delivery orders", "severity": "low"}
        else:
            impact = {"trend": "neutral", "message": "Normal traffic expected", "severity": "none"}
        
        return {
            "store_id": store_id,
            "location": _store_location(store),
            "temperature": round(temp),
            "condition": condition,
            "condition_label": condition_display["label"],
            "condition_icon": condition_display["icon"],
            "condition_color": condition_display["color"],
            "wind_speed": round(wind_speed),
            "is_day": weather.get("is_day", True),
            "sales_impact": impact,
            "timestamp": datetime.now().isoformat(),
        }
        
    except Exception as e:
        # Return mock data on error
        return {
            "store_id": store_id,
            "location": _store_location(store),
            "temperature": 65,
            "condition": "unknown",
            "condition_label": "Data Unavailable",
            "condition_icon": "🌤️",
            "condition_color": "gray",
            "wind_speed": 0,
            "is_day": True,
            "sales_impact": {"trend": "neutral", "message": "Weather data unavailable", "severity": "none"},
            "timestamp": datetime.now().isoformat(),
            "error": str(e),
        }


@router.get("/events/{store_id}")
async def get_local_events(
    request: Request,
    store_id: int,
    settings: Settings = Depends(get_settings),
) -> dict:
    """
    Get local events near a store location.
    
    Returns detailed event list from Ticketmaster API with dates, times, and venues.
    Shows up to 50 events for the next week, sorted by date.
    Uses client's local time for timestamps.
    """
    from services.demo_data import demo_data
    DEMO_STORES = demo_data.DEMO_STORES
    import math
    
    # Get client's adjusted time
    client_now = get_client_adjusted_time(request)
    
    # Find store location
    store = next((s for s in DEMO_STORES if s["store_id"] == store_id), DEMO_STORES[0])
    store_lat = store["lat"]
    store_lng = store["lng"]
    
    def haversine_distance(lat1, lon1, lat2, lon2):
        """Calculate distance in miles between two coordinates."""
        R = 3959  # Earth's radius in miles
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        return R * c
    
    try:
        events_data = await events_service.check_event_impact(
            store_lat, store_lng
        )
        
        # Format events for display with distance calculation
        formatted_events = []
        for event in events_data.get("events", []):
            # Try to get venue coordinates if available (Ticketmaster sometimes provides them)
            # For now, estimate based on city/venue - we'll approximate distances
            event_info = {
                "id": event.get("id"),
                "name": event.get("name"),
                "date": event.get("date"),
                "time": event.get("time"),
                "venue": event.get("venue"),
                "type": event.get("type"),
                "url": event.get("url"),
                "distance_miles": None,  # Will be approximated
            }
            formatted_events.append(event_info)
        
        # Sort events by date (primary) - already sorted by Ticketmaster API
        # We keep the date sort as primary
        formatted_events.sort(key=lambda x: (x.get("date") or "9999-99-99", x.get("time") or "99:99"))
        
        return {
            "store_id": store_id,
            "location": _store_location(store),
            "event_count": events_data.get("event_count", 0),
            "has_events": events_data.get("has_any_events", False),
            "traffic_impact": events_data.get("estimated_traffic_impact", "none"),
            "events": formatted_events,  # Return all events (up to 50)
            "sports_count": events_data.get("sports_count", 0),
            "music_count": events_data.get("music_count", 0),
            "timestamp": client_now.isoformat(),
        }
        
    except Exception as e:
        return {
            "store_id": store_id,
            "location": _store_location(store),
            "event_count": 0,
            "has_events": False,
            "traffic_impact": "none",
            "events": [],
            "error": str(e),
            "timestamp": client_now.isoformat(),
        }


@router.get("/staff/{store_id}")
async def get_staff_status(
    store_id: int,
    settings: Settings = Depends(get_settings),
) -> dict:
    """
    Get current staffing status for a store.
    
    Returns who's on duty, scheduled shifts, etc.
    """
    import random
    now = datetime.now()

    employees = [
        {"id": 1, "name": "Maria Garcia", "role": "shift_lead"},
        {"id": 2, "name": "John Davis", "role": "prep_cook"},
        {"id": 3, "name": "Sarah Kim", "role": "prep_cook"},
        {"id": 4, "name": "Mike Rodriguez", "role": "prep_cook"},
        {"id": 5, "name": "Emily Chen", "role": "cashier"},
    ]

    on_duty = random.sample(employees, random.randint(3, 5))
    
    return {
        "store_id": store_id,
        "timestamp": now.isoformat(),
        "on_duty": on_duty,
        "scheduled_count": len(on_duty) + random.randint(0, 2),
        "next_shift": {
            "time": (now + timedelta(hours=random.randint(1, 4))).strftime("%I:%M %p"),
            "employee": random.choice([e for e in employees if e not in on_duty])
        },
        "labor_hours_today": sum(random.uniform(4, 8) for _ in on_duty),
    }


