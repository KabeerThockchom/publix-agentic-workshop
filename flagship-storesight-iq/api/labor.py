"""
Labor Optimization API endpoints.

Provides staffing management and ML-powered optimization:
- Current schedule vs actuals
- Labor cost tracking
- ML-optimized staffing recommendations
- Employee availability management

Uses the labor-optimizer model serving endpoint.
"""

from typing import List, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
import logging
from config.settings import Settings, get_settings
from config.database import query_sql
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


# === Pydantic Models ===

class Employee(BaseModel):
    """Employee information."""
    id: int
    name: str
    role: str  # "shift_lead", "prep_cook", "cashier"
    hourly_rate: float
    status: str  # "on_duty", "scheduled", "off"


class Shift(BaseModel):
    """Single shift."""
    id: int
    employee_id: int
    employee_name: str
    role: str
    start_time: str
    end_time: str
    hours: float
    status: str  # "completed", "in_progress", "scheduled"


class HourlyLabor(BaseModel):
    """Hourly labor data."""
    hour: int
    hour_label: str
    scheduled_staff: int
    actual_staff: int
    forecasted_demand: int
    optimal_staff: int
    status: str  # "understaffed", "optimal", "overstaffed"


class LaborSummary(BaseModel):
    """Daily labor summary."""
    store_id: int
    date: str
    total_scheduled_hours: float
    total_actual_hours: float
    labor_cost: float
    labor_cost_pct: float  # As percentage of sales
    sales: float
    productivity: float  # Sales per labor hour


class StaffingRecommendation(BaseModel):
    """ML-generated staffing recommendation."""
    hour: int
    hour_label: str
    current_scheduled: int
    recommended_staff: int
    forecasted_demand: int
    confidence: float
    action: str  # "add_staff", "reduce_staff", "optimal"
    reason: str


# === Helper Functions ===

def format_hour(hour: int) -> str:
    """Format hour as readable string."""
    if hour == 0:
        return "12 AM"
    elif hour < 12:
        return f"{hour} AM"
    elif hour == 12:
        return "12 PM"
    else:
        return f"{hour - 12} PM"


# === Demo Data ===

DEMO_EMPLOYEES = [
    {"id": 1, "name": "Maria Garcia", "role": "shift_lead", "hourly_rate": 18.50},
    {"id": 2, "name": "John Davis", "role": "prep_cook", "hourly_rate": 16.00},
    {"id": 3, "name": "Sarah Kim", "role": "prep_cook", "hourly_rate": 16.00},
    {"id": 4, "name": "Mike Rodriguez", "role": "prep_cook", "hourly_rate": 15.50},
    {"id": 5, "name": "Emily Chen", "role": "cashier", "hourly_rate": 15.00},
    {"id": 6, "name": "David Park", "role": "prep_cook", "hourly_rate": 15.50},
    {"id": 7, "name": "Jessica Lee", "role": "shift_lead", "hourly_rate": 18.00},
    {"id": 8, "name": "Chris Brown", "role": "prep_cook", "hourly_rate": 16.00},
]


# === Endpoints ===

@router.get("/summary/{store_id}")
async def get_labor_summary(
    request: Request,
    store_id: int,
    date: Optional[str] = Query(None),
    settings: Settings = Depends(get_settings),
) -> LaborSummary:
    """
    Get labor summary for a store on a specific date.
    
    Returns hours worked, costs, and productivity metrics.
    """
    import random

    client_now = get_client_adjusted_time(request)
    target_date = date or client_now.strftime("%Y-%m-%d")
    
    # Simulate labor data
    total_scheduled = random.uniform(45, 60)
    total_actual = total_scheduled * random.uniform(0.95, 1.05)
    avg_rate = 16.00
    labor_cost = total_actual * avg_rate
    sales = random.uniform(2000, 3500)

    return LaborSummary(
        store_id=store_id,
        date=target_date,
        total_scheduled_hours=round(total_scheduled, 1),
        total_actual_hours=round(total_actual, 1),
        labor_cost=round(labor_cost, 2),
        labor_cost_pct=round((labor_cost / sales) * 100, 1),
        sales=round(sales, 2),
        productivity=round(sales / total_actual, 2),
    )


@router.get("/schedule/{store_id}")
async def get_schedule(
    request: Request,
    store_id: int,
    date: Optional[str] = Query(None),
    settings: Settings = Depends(get_settings),
) -> List[Shift]:
    """
    Get scheduled shifts for a store.
    
    Returns all shifts for the specified date.
    Uses client's local time to determine shift status (completed, in_progress, scheduled).
    
    Shift assignments are deterministic based on date (seeded random) to ensure
    consistency between Operations and Labor pages.
    """
    import random

    client_now = get_client_adjusted_time(request)
    target_date = date or client_now.strftime("%Y-%m-%d")
    current_hour = client_now.hour
    
    logger.info(f"Labor schedule request - client_hour={current_hour}, target_date={target_date}")

    # Use seeded random for consistent shift assignments within the same day
    # This ensures Operations page and Labor page show the same employees
    date_seed = int(client_now.strftime("%Y%m%d"))
    rng = random.Random(date_seed)
    
    shuffled = DEMO_EMPLOYEES.copy()
    rng.shuffle(shuffled)
    
    shifts = []
    shift_id = 1

    # Morning shift (6 AM - 2 PM) - first 3 employees
    morning_staff = shuffled[0:3]
    for emp in morning_staff:
        status = "completed" if current_hour >= 14 else ("in_progress" if current_hour >= 6 else "scheduled")
        shifts.append(Shift(
            id=shift_id,
            employee_id=emp["id"],
            employee_name=emp["name"],
            role=emp["role"],
            start_time="06:00 AM",
            end_time="02:00 PM",
            hours=8.0,
            status=status
        ))
        shift_id += 1

    # Mid shift (10 AM - 6 PM) - next 2 employees
    mid_staff = shuffled[3:5]
    for emp in mid_staff:
        status = "completed" if current_hour >= 18 else ("in_progress" if current_hour >= 10 else "scheduled")
        shifts.append(Shift(
            id=shift_id,
            employee_id=emp["id"],
            employee_name=emp["name"],
            role=emp["role"],
            start_time="10:00 AM",
            end_time="06:00 PM",
            hours=8.0,
            status=status
        ))
        shift_id += 1

    # Evening shift (2 PM - 10 PM) - last 3 employees
    evening_staff = shuffled[5:8]
    for emp in evening_staff:
        status = "completed" if current_hour >= 22 else ("in_progress" if current_hour >= 14 else "scheduled")
        shifts.append(Shift(
            id=shift_id,
            employee_id=emp["id"],
            employee_name=emp["name"],
            role=emp["role"],
            start_time="02:00 PM",
            end_time="10:00 PM",
            hours=8.0,
            status=status
        ))
        shift_id += 1

    return shifts


class HourlyLaborWithRecommendations(BaseModel):
    """Combined response with hourly data and recommendations."""
    hourly: List[HourlyLabor]
    recommendations: List[StaffingRecommendation]


# In-memory cache to ensure consistency between endpoints
_labor_cache: dict = {}


def _get_cache_key(store_id: int, date: str) -> str:
    return f"{store_id}_{date}"


def _fallback_optimal(hour: int) -> int:
    """Fallback optimal staffing when model is unavailable."""
    if 11 <= hour < 14:
        return 6
    elif 17 <= hour < 20:
        return 5
    else:
        return 3


async def _fetch_labor_data(
    store_id: int,
    target_date: str,
    settings: Settings,
    client_hour: Optional[int] = None,
) -> List[HourlyLabor]:
    """
    Core function to fetch all hourly labor data.
    Called once and cached to ensure consistency.
    
    Args:
        client_hour: Client's local hour from X-Client-Local-Hour header
    """
    import random
    
    server_hour = datetime.now().hour
    current_hour = client_hour if client_hour is not None else server_hour
    logger.info(f"Fetching labor data - server_hour={server_hour}, client_hour={client_hour}, using={current_hour}")
    warehouse_id = settings.databricks_warehouse_id

    hourly_data = []
    schedule_data = {}
    demand_data = {}

    # Try to fetch scheduled/actual staff from SQL Warehouse
    if warehouse_id:
        try:
            # Anchor to the latest date present in the table rather than the
            # literal calendar `target_date`: the synthetic data set is static
            # and ends at generation day, so filtering on "today" would return
            # nothing a day later and silently fall back to simulated staffing.
            schedule_query = f"""
                SELECT hour, scheduled_staff, actual_staff
                FROM {settings.get_table_path('labor_schedule')}
                WHERE store_id = {store_id}
                  AND date = (SELECT MAX(date) FROM {settings.get_table_path('labor_schedule')})
                ORDER BY hour
            """
            schedule_results = query_sql(schedule_query, warehouse_id)
            for row in schedule_results:
                schedule_data[row['hour']] = {
                    'scheduled': row['scheduled_staff'],
                    'actual': row['actual_staff']
                }
            logger.info(f"Loaded {len(schedule_data)} hours of schedule data from SQL Warehouse")
        except Exception as e:
            logger.warning(f"Could not fetch labor schedule from SQL Warehouse: {e}")

        try:
            # Same anchoring as the schedule query — use the most recent day of
            # POS data so the hourly demand curve reflects real transactions
            # instead of collapsing to the simulated fallback once the data ages.
            demand_query = f"""
                SELECT
                    HOUR(timestamp) as hour,
                    COUNT(*) as transactions
                FROM {settings.get_table_path('pos_transactions')}
                WHERE store_id = {store_id}
                  AND DATE(timestamp) = (SELECT MAX(DATE(timestamp)) FROM {settings.get_table_path('pos_transactions')})
                GROUP BY HOUR(timestamp)
                ORDER BY hour
            """
            demand_results = query_sql(demand_query, warehouse_id)
            for row in demand_results:
                demand_data[row['hour']] = row['transactions']
            logger.info(f"Loaded demand data for {len(demand_data)} hours from SQL Warehouse")
        except Exception as e:
            logger.warning(f"Could not fetch demand data from SQL Warehouse: {e}")

    # Generate hourly data with real SQL data + model serving for optimal
    for hour in range(6, 22):
        # Get scheduled staff from SQL or fallback
        if hour in schedule_data:
            scheduled = schedule_data[hour]['scheduled']
            actual = schedule_data[hour]['actual'] if schedule_data[hour]['actual'] is not None else scheduled
        else:
            if 11 <= hour < 14:
                scheduled = random.randint(5, 7)
            elif 17 <= hour < 20:
                scheduled = random.randint(4, 6)
            else:
                scheduled = random.randint(2, 4)
            actual = scheduled if hour > current_hour else scheduled + random.randint(-1, 1)
            actual = max(1, actual)

        # Get demand from SQL or simulate
        if hour in demand_data:
            demand = demand_data[hour]
        else:
            if 11 <= hour < 14:
                demand = random.randint(30, 45)
            elif 17 <= hour < 20:
                demand = random.randint(20, 35)
            else:
                demand = random.randint(8, 18)

        # Call model serving for optimal staff recommendation
        try:
            result = await model_client.predict_labor(
                store_id=store_id,
                date=target_date,
                hour=hour,
                forecasted_transactions=demand,
                avg_ticket=24.00,
            )
            predictions = result.get("predictions", [])
            if predictions and len(predictions) > 0:
                staff_level_0indexed = int(predictions[0]) if isinstance(predictions[0], (int, float)) else 2
                optimal = staff_level_0indexed + 2
                optimal = max(2, min(8, optimal))
            else:
                optimal = _fallback_optimal(hour)
        except Exception as e:
            logger.warning(f"Model serving unavailable for hour {hour}: {e}")
            optimal = _fallback_optimal(hour)

        # Determine status
        if scheduled < optimal - 1:
            status = "understaffed"
        elif scheduled > optimal + 1:
            status = "overstaffed"
        else:
            status = "optimal"

        hourly_data.append(HourlyLabor(
            hour=hour,
            hour_label=format_hour(hour),
            scheduled_staff=scheduled,
            actual_staff=actual,
            forecasted_demand=demand,
            optimal_staff=optimal,
            status=status
        ))

    return hourly_data


def _derive_recommendations(hourly_data: List[HourlyLabor]) -> List[StaffingRecommendation]:
    """Derive recommendations from hourly data - NO separate API calls."""
    hourly_by_hour = {h.hour: h for h in hourly_data}
    
    analysis_hours = [11, 12, 13, 17, 18, 19]
    hour_reasons = {
        11: "Lunch rush starting",
        12: "Peak lunch hour",
        13: "Post-lunch transition",
        17: "Dinner rush starting",
        18: "Peak dinner period",
        19: "Dinner wind-down",
    }

    recommendations = []
    
    for hour in analysis_hours:
        if hour not in hourly_by_hour:
            continue
            
        hourly = hourly_by_hour[hour]
        base_reason = hour_reasons.get(hour, "Scheduled period")
        
        current_scheduled = hourly.scheduled_staff
        recommended = hourly.optimal_staff
        forecasted_demand = hourly.forecasted_demand
        
        if recommended > current_scheduled:
            action = "add_staff"
            reason = f"{base_reason} - add {recommended - current_scheduled} staff for faster service"
        elif recommended < current_scheduled:
            action = "reduce_staff"
            reason = f"{base_reason} - can reduce by {current_scheduled - recommended} staff"
        else:
            action = "optimal"
            reason = f"{base_reason} - staffing is optimal"

        recommendations.append(StaffingRecommendation(
            hour=hour,
            hour_label=format_hour(hour),
            current_scheduled=current_scheduled,
            recommended_staff=recommended,
            forecasted_demand=forecasted_demand,
            confidence=0.88,
            action=action,
            reason=reason
        ))

    return recommendations


@router.get("/hourly/{store_id}")
async def get_hourly_labor(
    request: Request,
    store_id: int,
    date: Optional[str] = Query(None),
    settings: Settings = Depends(get_settings),
) -> List[HourlyLabor]:
    """
    Get hourly labor breakdown.
    
    Data sources:
    - Scheduled/Actual: labor_schedule table in Unity Catalog
    - Demand: pos_transactions table in Unity Catalog  
    - Optimal: labor optimizer model serving endpoint
    
    Results are cached to ensure consistency with recommendations.
    Uses client's local time from X-Client-Local-Hour header.
    """
    global _labor_cache
    
    client_now = get_client_adjusted_time(request)
    target_date = date or client_now.strftime("%Y-%m-%d")
    
    # Get client hour for data generation
    client_hour = None
    header_value = request.headers.get("X-Client-Local-Hour") if request else None
    if header_value:
        try:
            client_hour = int(header_value)
        except ValueError:
            pass
    
    cache_key = _get_cache_key(store_id, target_date)
    
    # Check cache first (valid for 60 seconds)
    if cache_key in _labor_cache:
        cached_time, cached_data = _labor_cache[cache_key]
        if (datetime.now() - cached_time).seconds < 60:
            logger.info(f"Using cached labor data for {cache_key}")
            return cached_data
    
    # Fetch fresh data with client hour
    hourly_data = await _fetch_labor_data(store_id, target_date, settings, client_hour=client_hour)
    
    # Cache the result
    _labor_cache[cache_key] = (datetime.now(), hourly_data)
    
    # Clean old cache entries
    old_keys = [k for k, (t, _) in _labor_cache.items() if (datetime.now() - t).seconds > 120]
    for k in old_keys:
        del _labor_cache[k]
    
    return hourly_data


@router.get("/recommendations/{store_id}")
async def get_staffing_recommendations(
    request: Request,
    store_id: int,
    date: Optional[str] = Query(None),
    settings: Settings = Depends(get_settings),
) -> List[StaffingRecommendation]:
    """
    Get ML-optimized staffing recommendations.
    
    USES THE SAME CACHED DATA as get_hourly_labor to ensure consistency.
    Recommendations are derived from the hourly data, not fetched separately.
    Uses client's local time from X-Client-Local-Hour header.
    """
    # This will use cached data if available, ensuring consistency
    hourly_data = await get_hourly_labor(request, store_id, date, settings)
    
    # Derive recommendations from the SAME data
    return _derive_recommendations(hourly_data)


@router.get("/employees/{store_id}")
async def get_employees(
    store_id: int,
    settings: Settings = Depends(get_settings),
) -> List[Employee]:
    """
    Get all employees for a store.
    
    Returns employee roster with current status.
    """
    import random

    employees = []
    for emp in DEMO_EMPLOYEES:
        status = random.choice(["on_duty", "scheduled", "off"])
        employees.append(Employee(
            id=emp["id"],
            name=emp["name"],
            role=emp["role"],
            hourly_rate=emp["hourly_rate"],
            status=status
        ))

    return employees


@router.post("/optimize/{store_id}")
async def optimize_staffing(
    store_id: int,
    date: str,
    settings: Settings = Depends(get_settings),
) -> dict:
    """
    Run ML optimization for staffing on a specific date.
    
    Calls the labor optimizer model serving endpoint.
    """
    import random

    # Try to call model serving endpoint
    try:
        # Get forecast first
        from api.forecast import get_daypart_forecast
        forecast = await get_daypart_forecast(store_id, date, settings)
        total_demand = forecast.get("total_predicted_transactions", 200)

        # Build hourly recommendations
        hourly_staff = []
        for hour in range(6, 22):
            result = await model_client.predict_labor(
                store_id=store_id,
                date=date,
                hour=hour,
                forecasted_transactions=int(total_demand / 16),  # Rough hourly
                avg_ticket=24.00,
            )
            # Model returns 0-indexed staff level (0-6), add 2 to get actual (2-8)
            predictions = result.get("predictions", [])
            if predictions:
                staff_level = int(predictions[0]) + 2
                staff_level = max(2, min(8, staff_level))
            else:
                staff_level = 4
            hourly_staff.append({
                "hour": hour,
                "recommended": staff_level
            })

        return {
            "store_id": store_id,
            "date": date,
            "optimized_schedule": hourly_staff,
            "total_hours": sum(h["recommended"] for h in hourly_staff),
            "estimated_labor_cost": sum(h["recommended"] for h in hourly_staff) * 16.00,
            "model_status": "active"
        }

    except Exception:
        # Return simulated optimization
        hourly_staff = []
        for hour in range(6, 22):
            if 11 <= hour < 14:
                staff = random.randint(5, 7)
            elif 17 <= hour < 20:
                staff = random.randint(4, 6)
            else:
                staff = random.randint(2, 4)
            hourly_staff.append({"hour": hour, "recommended": staff})

        return {
            "store_id": store_id,
            "date": date,
            "optimized_schedule": hourly_staff,
            "total_hours": sum(h["recommended"] for h in hourly_staff),
            "estimated_labor_cost": sum(h["recommended"] for h in hourly_staff) * 16.00,
            "model_status": "simulated"
        }


