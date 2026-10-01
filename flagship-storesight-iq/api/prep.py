"""
Prep Scheduler (production-prep) API endpoints.

Provides ML-optimized prep schedules for QSR stores:
- Current prepped-item inventory by prep subtype
- Optimal prep/pull schedule by time of day
- Real-time adjustments based on forecasted demand

Uses the prep-scheduler model serving endpoint. Accounts for prep times and
prepped-item usable windows. The prep-subtype taxonomy is sourced from the
single-source domain loader (config/domain.py). NOTE: response/DB field names
(e.g. `crust_type`) are retained for frontend + Lakebase-DB compatibility.
"""

from typing import List, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
import logging
from config.settings import Settings, get_settings
from config.domain import domain
from services.model_serving import model_client

logger = logging.getLogger(__name__)

router = APIRouter()


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


# === Prep Subtypes with Properties (sourced from the domain taxonomy) ===
# `name`/`bake_time_minutes` field names retained for wire compatibility.
CRUST_TYPES = [
    {
        "id": s["id"],
        "name": s["label"],
        "bake_time_minutes": s["prep_time_min"],
        "freshness_hours": s["freshness_hours"],
        "popularity": s["popularity"],
        "description": s.get("label", ""),
    }
    for s in domain.prep_subtypes()
]

# Map display subtype names to model serving subtype keys.
CRUST_NAME_MAP = {s["label"]: s["key"] for s in domain.prep_subtypes()}


# === Pydantic Models ===

class DoughInventory(BaseModel):
    """Current prepped dough-ball inventory for a crust type."""
    crust_type: str
    quantity: int
    freshness_status: str  # "fresh", "aging", "expired"
    hours_until_stale: float
    last_prepped: str


class PrepTask(BaseModel):
    """Single dough-prep task."""
    id: int
    crust_type: str
    quantity: int
    scheduled_time: str
    ready_time: str
    status: str  # "pending", "prepping", "complete"
    priority: str  # "high", "medium", "low"


class PrepSchedule(BaseModel):
    """Full dough-prep schedule for a day."""
    store_id: int
    date: str
    tasks: List[PrepTask]
    total_dough_balls: int
    next_prep: Optional[PrepTask]


class PrepRecommendation(BaseModel):
    """ML recommendation for dough prep."""
    crust_type: str
    recommended_quantity: int
    suggested_prep_time: str
    reason: str
    confidence: float


# === Endpoints ===

@router.get("/inventory/{store_id}")
async def get_dough_inventory(
    request: Request,
    store_id: int,
    settings: Settings = Depends(get_settings),
) -> List[DoughInventory]:
    """
    Get current prepped dough-ball inventory for a store.

    Uses shared demo_data service for consistent levels.
    Shows quantity and freshness for each crust type.
    """
    from services.demo_data import demo_data

    client_now = get_client_adjusted_time(request)
    current_hour = client_now.hour
    date_str = client_now.strftime("%Y-%m-%d")

    dough_items = demo_data.get_dough_inventory(store_id, date_str, current_hour)

    inventory = []
    for item in dough_items:
        prepped_time = client_now.replace(hour=item.last_prepped_hour, minute=0, second=0)

        inventory.append(DoughInventory(
            crust_type=item.crust_type,
            quantity=item.quantity,
            freshness_status=item.freshness_status,
            hours_until_stale=item.hours_until_stale,
            last_prepped=prepped_time.strftime("%I:%M %p")
        ))

    return inventory


@router.get("/schedule/{store_id}")
async def get_prep_schedule(
    request: Request,
    store_id: int,
    date: Optional[str] = Query(None),
    settings: Settings = Depends(get_settings),
) -> PrepSchedule:
    """
    Get dough-prep schedule for a day.

    Returns all scheduled prep pulls with times and quantities.
    Uses client's local time to determine task status.
    """
    import random

    client_now = get_client_adjusted_time(request)
    target_date = date or client_now.strftime("%Y-%m-%d")
    current_hour = client_now.hour

    logger.info(f"Prep schedule request - client_hour={current_hour}")

    tasks = []
    task_id = 1

    # Standard prep pull schedule
    prep_times = [
        ("10:00", "Opening prep"),
        ("14:00", "Afternoon pull"),
        ("16:30", "Pre-dinner build-up"),
        ("20:00", "Late-night top-off"),
    ]

    for prep_time_str, reason in prep_times:
        prep_hour = int(prep_time_str.split(":")[0])

        if date is None:  # Today
            if prep_hour < current_hour - 1:
                status = "complete"
            elif prep_hour <= current_hour:
                status = "prepping"
            else:
                status = "pending"
        else:
            status = "pending"

        for crust in CRUST_TYPES[:3]:  # Top 3 crusts at each prep
            qty = int(40 * crust["popularity"] * random.uniform(0.8, 1.2))

            prep_dt = datetime.strptime(f"{target_date} {prep_time_str}", "%Y-%m-%d %H:%M")
            ready_dt = prep_dt + timedelta(minutes=20)  # prepped item ready

            tasks.append(PrepTask(
                id=task_id,
                crust_type=crust["name"],
                quantity=qty,
                scheduled_time=prep_dt.strftime("%I:%M %p"),
                ready_time=ready_dt.strftime("%I:%M %p"),
                status=status,
                priority="high" if "dinner" in reason.lower() else "medium"
            ))
            task_id += 1

    next_prep = next((t for t in tasks if t.status == "pending"), None)

    return PrepSchedule(
        store_id=store_id,
        date=target_date,
        tasks=tasks,
        total_dough_balls=sum(t.quantity for t in tasks),
        next_prep=next_prep
    )


@router.get("/recommendations/{store_id}")
async def get_prep_recommendations(
    request: Request,
    store_id: int,
    settings: Settings = Depends(get_settings),
) -> List[PrepRecommendation]:
    """
    Get ML-optimized dough-prep recommendations.

    Attempts to call the Databricks Model Serving endpoint.
    Analyzes current inventory, forecast, and time of day.
    """
    import random

    client_now = get_client_adjusted_time(request)
    hour = client_now.hour
    target_date = client_now.strftime("%Y-%m-%d")

    logger.info(f"Prep recommendations request - client_hour={hour}")

    recommendations = []

    # Determine next rush period based on client's local time
    if hour < 14:
        rush = "lunch"
        rush_time = "12:00 PM"
    elif hour < 20:
        rush = "dinner"
        rush_time = "6:00 PM"
    else:
        rush = "late night"
        rush_time = "10:00 PM"

    from services.demo_data import demo_data
    dough_items = demo_data.get_dough_inventory(store_id, target_date, hour)
    current_inv = {b.crust_type: b.quantity for b in dough_items}

    # Estimate hourly traffic across the operating day
    hourly_traffic = [5] * 10 + [12, 18, 22, 18, 14, 12, 14, 28, 40, 40, 32, 18, 10, 6]

    model_used = False

    try:
        for crust in CRUST_TYPES:
            crust_key = CRUST_NAME_MAP.get(crust["name"], next(iter(CRUST_NAME_MAP.values())))

            if rush == "lunch":
                target_hour = 12
            elif rush == "dinner":
                target_hour = 18
            else:
                target_hour = 22
            target_traffic = hourly_traffic[target_hour] if len(hourly_traffic) > target_hour else 30

            result = await model_client.predict_prep_schedule(
                store_id=store_id,
                date=target_date,
                hour=target_hour,
                subtype_key=crust_key,
                forecasted_traffic=target_traffic,
                max_traffic=50,
            )

            predictions = result.get("predictions", [])
            if predictions and len(predictions) > 0:
                raw_qty = predictions[0] if isinstance(predictions[0], (int, float)) else 10
                scaled_qty = raw_qty * (1 + target_traffic / 50) * (1 + crust["popularity"])
                qty = int(max(3, min(45, scaled_qty)))
                model_used = True

                # Suggested prep time = ~30 min before the rush
                if rush == "lunch":
                    suggested_time = "11:30 AM"
                elif rush == "dinner":
                    suggested_time = "5:30 PM"
                else:
                    suggested_time = "9:30 PM"

                recommendations.append(PrepRecommendation(
                    crust_type=crust["name"],
                    recommended_quantity=qty,
                    suggested_prep_time=suggested_time,
                    reason=f"ML-optimized for {rush} rush. Based on traffic forecast.",
                    confidence=0.88
                ))
                logger.info(f"Prep model prediction for {crust['name']}: {qty} items")
    except Exception as e:
        logger.warning(f"Prep model unavailable, using fallback: {e}")

    if not recommendations:
        for crust in CRUST_TYPES:
            if rush == "lunch":
                base_qty = int(35 * crust["popularity"])
            elif rush == "dinner":
                base_qty = int(55 * crust["popularity"])
            else:
                base_qty = int(25 * crust["popularity"])

            suggested_time = (client_now + timedelta(minutes=10)).strftime("%I:%M %p")

            recommendations.append(PrepRecommendation(
                crust_type=crust["name"],
                recommended_quantity=base_qty,
                suggested_prep_time=suggested_time,
                reason=f"Prep for {rush} rush at {rush_time}. Usable window {crust['freshness_hours']}h.",
                confidence=random.uniform(0.82, 0.95)
            ))

    recommendations.sort(key=lambda x: x.recommended_quantity, reverse=True)

    return recommendations


@router.post("/optimize/{store_id}")
async def optimize_prep_schedule(
    store_id: int,
    date: str,
    settings: Settings = Depends(get_settings),
) -> dict:
    """
    Generate ML-optimized dough-prep schedule for a day.

    Calls the prep scheduler model serving endpoint.
    """
    import random

    from services.demo_data import demo_data
    dough_items = demo_data.get_dough_inventory(store_id, date, 12)
    current_inv = {b.crust_type: b.quantity for b in dough_items}

    hourly_traffic = [random.randint(5, 45) for _ in range(24)]

    prep_times_config = [
        (10, "10:00 AM", "Opening prep"),
        (14, "02:00 PM", "Afternoon pull"),
        (16, "04:30 PM", "Pre-dinner build-up"),
        (20, "08:00 PM", "Late-night top-off"),
    ]

    try:
        optimized_schedule = []

        for prep_hour, time_str, _ in prep_times_config:
            traffic = hourly_traffic[prep_hour] if prep_hour < len(hourly_traffic) else 25

            for crust in CRUST_TYPES[:3]:
                crust_key = CRUST_NAME_MAP.get(crust["name"], next(iter(CRUST_NAME_MAP.values())))

                result = await model_client.predict_prep_schedule(
                    store_id=store_id,
                    date=date,
                    hour=prep_hour,
                    subtype_key=crust_key,
                    forecasted_traffic=traffic,
                    max_traffic=50,
                )

                predictions = result.get("predictions", [])
                if predictions and len(predictions) > 0:
                    raw_qty = predictions[0] if isinstance(predictions[0], (int, float)) else 10
                    scaled_qty = raw_qty * (1 + traffic / 50) * (1 + crust["popularity"])
                    qty = int(max(3, min(45, scaled_qty)))

                    optimized_schedule.append({
                        "time": time_str,
                        "crust_type": crust["name"],
                        "quantity": qty
                    })

        logger.info(f"Prep schedule optimized via model serving for {date}")

        return {
            "store_id": store_id,
            "date": date,
            "optimized_schedule": optimized_schedule,
            "total_dough_balls": sum(s["quantity"] for s in optimized_schedule),
            "model_status": "active"
        }

    except Exception as e:
        logger.warning(f"Prep model unavailable, using fallback: {e}")
        schedule = [
            {"time": "10:00 AM", "crust_type": "Original", "quantity": 20},
            {"time": "10:00 AM", "crust_type": "Thin Crust", "quantity": 8},
            {"time": "02:00 PM", "crust_type": "Original", "quantity": 18},
            {"time": "02:00 PM", "crust_type": "Pan", "quantity": 10},
            {"time": "04:30 PM", "crust_type": "Original", "quantity": 30},
            {"time": "04:30 PM", "crust_type": "Stuffed Crust", "quantity": 12},
            {"time": "04:30 PM", "crust_type": "Thin Crust", "quantity": 14},
            {"time": "08:00 PM", "crust_type": "Original", "quantity": 22},
            {"time": "08:00 PM", "crust_type": "Pan", "quantity": 10},
        ]

        return {
            "store_id": store_id,
            "date": date,
            "optimized_schedule": schedule,
            "total_dough_balls": sum(s["quantity"] for s in schedule),
            "estimated_waste_reduction": f"{random.randint(10, 25)}%",
            "model_status": "simulated"
        }


@router.get("/alerts/{store_id}")
async def get_prep_alerts(
    request: Request,
    store_id: int,
    settings: Settings = Depends(get_settings),
) -> List[dict]:
    """
    Get dough/prep-related alerts for a store.

    Returns low stock and dough freshness warnings.
    """
    inventory = await get_dough_inventory(request, store_id, settings)

    alerts = []

    for dough in inventory:
        if dough.quantity < 5:
            alerts.append({
                "type": "low_stock",
                "severity": "warning",
                "crust_type": dough.crust_type,
                "message": f"{dough.crust_type} prep running low ({dough.quantity} remaining)",
                "action": f"Prep {max(0, 12 - dough.quantity)} more"
            })

        if dough.freshness_status == "aging":
            alerts.append({
                "type": "freshness",
                "severity": "info",
                "crust_type": dough.crust_type,
                "message": f"{dough.crust_type} prep aging ({dough.hours_until_stale:.1f}h until unusable)",
                "action": "Use first or re-tray"
            })

        if dough.freshness_status == "expired":
            alerts.append({
                "type": "waste",
                "severity": "critical",
                "crust_type": dough.crust_type,
                "message": f"{dough.crust_type} prep past usable window",
                "action": "Mark as waste and re-prep"
            })

    return alerts
