"""
Demand Forecasting API endpoints.

Provides ML-powered demand predictions:
- 7-day demand forecast
- Hourly breakdown by daypart
- Weather and event impact factors
- Prep recommendations

Uses the demand-forecast model serving endpoint.
"""

from typing import List, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
import logging
from config.settings import Settings, get_settings
from services.model_serving import model_client
from services.external_apis import weather_service, events_service
from config.domain import domain

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

class DailyForecast(BaseModel):
    """Daily demand forecast."""
    date: str
    day_of_week: str
    predicted_transactions: int
    predicted_revenue: float
    confidence: float
    weather_impact: str  # "positive", "negative", "neutral"
    event_impact: str


class HourlyForecast(BaseModel):
    """Hourly demand forecast."""
    hour: int
    hour_label: str  # "6 AM", "12 PM", etc.
    daypart: str  # "lunch", "afternoon", "dinner", "late_night"
    predicted_transactions: int
    predicted_revenue: float
    confidence: float


class PrepRecommendation(BaseModel):
    """Prep recommendation based on forecast."""
    item: str
    quantity: int
    prep_time: str
    priority: str  # "high", "medium", "low"


class ForecastSummary(BaseModel):
    """Complete forecast summary for a store."""
    store_id: int
    generated_at: str
    daily_forecasts: List[DailyForecast]
    model_accuracy: float
    factors: dict


# === Helper Functions ===

def get_daypart(hour: int) -> str:
    """Determine daypart name from hour (sourced from the domain taxonomy)."""
    dp = domain.daypart_for(hour)
    return dp["name"] if dp else "closed"


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


# === Endpoints ===

@router.get("/weekly/{store_id}")
async def get_weekly_forecast(
    request: Request,
    store_id: int,
    settings: Settings = Depends(get_settings),
) -> ForecastSummary:
    """
    Get 7-day demand forecast for a store.
    
    Attempts to call the Databricks Model Serving endpoint.
    Falls back to simulated predictions if endpoint is unavailable.
    Uses client's local time as the starting point for the 7-day forecast.
    """
    from services.demo_data import demo_data
    DEMO_STORES = demo_data.DEMO_STORES
    import random

    now = get_client_adjusted_time(request)
    store = next((s for s in DEMO_STORES if s["store_id"] == store_id), DEMO_STORES[0])

    # Get weather forecast
    weather_forecast = []
    try:
        weather_forecast = await weather_service.get_forecast(
            store["lat"], store["lng"], days=7
        )
    except Exception:
        pass

    daily_forecasts = []
    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    model_used = False

    for i in range(7):
        forecast_date = now + timedelta(days=i)
        day_name = day_names[forecast_date.weekday()]
        
        # Weather data for this day
        weather_temp = 70.0
        weather_condition = "clear"
        if i < len(weather_forecast):
            w = weather_forecast[i]
            weather_temp = w.get("temp_high", 70)
            weather_condition = w.get("condition", "clear")
        
        # Check for events
        is_event_day = False
        event_impact = "none"
        try:
            events = await events_service.check_event_impact(
                store["lat"], store["lng"], 
                forecast_date.strftime("%Y-%m-%d")
            )
            is_event_day = events["has_major_event"]
            if is_event_day:
                event_impact = events["estimated_traffic_impact"]
        except Exception:
            pass

        # Try calling Model Serving endpoint
        try:
            # Call real Databricks Model Serving endpoint
            # The model expects temporal + lag features, which are computed from the date
            result = await model_client.predict_demand(
                store_id=store_id,
                date=forecast_date.strftime("%Y-%m-%d"),
                base_transactions=200,  # Historical baseline
                base_revenue=2500.0,
            )
            
            # Parse model response - predictions is a list of floats (transaction counts)
            predictions = result.get("predictions", [])
            if predictions and len(predictions) > 0:
                # Model returns raw transaction count prediction
                base_txn = int(predictions[0]) if isinstance(predictions[0], (int, float)) else 200
                base_revenue = base_txn * 24.0  # Average prep ticket
                confidence = 0.88
                model_used = True
                logger.info(f"Model prediction for {forecast_date.date()}: {base_txn} transactions")
        except Exception as e:
            logger.warning(f"Model serving unavailable, using fallback: {e}")
            # Fallback to simulated predictions
            if forecast_date.weekday() < 5:  # Weekday
                base_txn = random.randint(180, 250)
                base_revenue = base_txn * random.uniform(11, 14)
            else:  # Weekend
                base_txn = random.randint(150, 200)
                base_revenue = base_txn * random.uniform(12, 15)
            confidence = random.uniform(0.82, 0.95)

        # Weather impact adjustments
        weather_impact = "neutral"
        if weather_condition in ["rain", "heavy_rain", "thunderstorm"]:
            weather_impact = "negative"
            if not model_used:
                base_txn = int(base_txn * 0.9)
        elif weather_temp > 85:
            weather_impact = "positive"
            if not model_used:
                base_txn = int(base_txn * 1.1)

        # Event impact adjustments (if not using model)
        if not model_used and event_impact == "high":
            base_txn = int(base_txn * 1.25)
        elif not model_used and event_impact == "medium":
            base_txn = int(base_txn * 1.15)

        daily_forecasts.append(DailyForecast(
            date=forecast_date.strftime("%Y-%m-%d"),
            day_of_week=day_name,
            predicted_transactions=int(base_txn),
            predicted_revenue=round(float(base_revenue), 2),
            confidence=float(confidence),
            weather_impact=weather_impact,
            event_impact=event_impact
        ))

    return ForecastSummary(
        store_id=store_id,
        generated_at=now.isoformat(),
        daily_forecasts=daily_forecasts,
        model_accuracy=0.89 if model_used else random.uniform(0.85, 0.92),
        factors={
            "weather_enabled": len(weather_forecast) > 0,
            "events_enabled": True,
            "seasonality": "winter",
            "trend": "stable",
            "model_serving": "connected" if model_used else "simulated"
        }
    )


@router.get("/hourly/{store_id}")
async def get_hourly_forecast(
    request: Request,
    store_id: int,
    date: Optional[str] = Query(None, description="Date in YYYY-MM-DD format"),
    settings: Settings = Depends(get_settings),
) -> List[HourlyForecast]:
    """
    Get hourly demand forecast for a specific date.
    
    Attempts to call the Databricks Model Serving endpoint for each hour.
    Falls back to simulated predictions if endpoint is unavailable.
    
    Returns predictions for each operating hour.
    Uses client's local time if no date is specified.
    """
    import random

    client_now = get_client_adjusted_time(request)
    target_date = datetime.strptime(date, "%Y-%m-%d") if date else client_now
    is_weekend = target_date.weekday() >= 5
    date_str = target_date.strftime("%Y-%m-%d")
    
    from services.demo_data import demo_data
    
    # Try to get model-based predictions for each hour
    model_used = False
    hourly_forecasts = []
    
    # Get forecast data from shared service (consistent with Operations page)
    forecast_data = demo_data.get_forecast_for_date(store_id, date_str)
    daily_baseline = forecast_data["predicted_transactions"]
    
    # First, try to get daily forecast from model to override
    try:
        result = await model_client.predict_demand(
            store_id=store_id,
            date=date_str,
            base_transactions=daily_baseline,
            base_revenue=forecast_data["predicted_revenue"],
        )
        predictions = result.get("predictions", [])
        if predictions and len(predictions) > 0:
            daily_baseline = int(predictions[0]) if isinstance(predictions[0], (int, float)) else daily_baseline
            model_used = True
            logger.info(f"Hourly forecast using model baseline: {daily_baseline} transactions/day")
    except Exception as e:
        logger.warning(f"Model serving unavailable for hourly forecast, using shared baseline: {e}")

    # Use shared hourly pattern from demo_data
    hourly_patterns = demo_data.HOURLY_TRAFFIC_PATTERN
    
    # Get daily sales for consistent hourly breakdown
    daily_sales = demo_data.get_daily_sales(store_id, date_str)

    for hour in range(demo_data.STORE_OPEN, demo_data.STORE_CLOSE):  # 10 AM to 11 PM
        daypart = get_daypart(hour)
        pattern_weight = hourly_patterns.get(hour, 0.05)
        
        if model_used:
            # Use model-derived baseline distributed by hourly pattern
            base_txn = int(daily_baseline * pattern_weight)
            confidence = 0.88
        else:
            # Use consistent hourly data from shared service
            base_txn = daily_sales.hourly_transactions.get(hour, int(daily_baseline * pattern_weight))
            confidence = 0.85

        hourly_forecasts.append(HourlyForecast(
            hour=hour,
            hour_label=format_hour(hour),
            daypart=daypart,
            predicted_transactions=max(1, base_txn),
            predicted_revenue=round(base_txn * daily_sales.avg_ticket, 2),
            confidence=float(confidence)
        ))

    return hourly_forecasts


@router.get("/daypart/{store_id}")
async def get_daypart_forecast(
    request: Request,
    store_id: int,
    date: Optional[str] = Query(None),
    settings: Settings = Depends(get_settings),
) -> dict:
    """
    Get demand forecast broken down by daypart.
    
    Uses shared demo_data service for consistent numbers.
    Summarizes lunch, afternoon, dinner, late night.
    Uses client's local time if no date is specified.
    """
    from services.demo_data import demo_data

    client_now = get_client_adjusted_time(request)
    target_date = datetime.strptime(date, "%Y-%m-%d") if date else client_now
    date_str = target_date.strftime("%Y-%m-%d")

    # Get consistent daily sales data
    daily_sales = demo_data.get_daily_sales(store_id, date_str)
    
    # Sum up transactions by daypart from consistent hourly data
    lunch_txn = sum(daily_sales.hourly_transactions.get(h, 0) for h in range(10, 14))
    afternoon_txn = sum(daily_sales.hourly_transactions.get(h, 0) for h in range(14, 17))
    dinner_txn = sum(daily_sales.hourly_transactions.get(h, 0) for h in range(17, 21))
    late_night_txn = sum(daily_sales.hourly_transactions.get(h, 0) for h in range(21, 24))

    dayparts = {
        "lunch": {"hours": "10 AM-2 PM", "transactions": lunch_txn, "peak_hour": "12 PM"},
        "afternoon": {"hours": "2-5 PM", "transactions": afternoon_txn, "peak_hour": "3 PM"},
        "dinner": {"hours": "5-9 PM", "transactions": dinner_txn, "peak_hour": "6 PM"},
        "late_night": {"hours": "9 PM-close", "transactions": late_night_txn, "peak_hour": "9 PM"},
    }

    total_txn = daily_sales.forecast_transactions
    avg_ticket = daily_sales.avg_ticket

    return {
        "store_id": store_id,
        "date": date_str,
        "dayparts": dayparts,
        "total_predicted_transactions": total_txn,
        "total_predicted_revenue": round(total_txn * avg_ticket, 2),
        "busiest_daypart": "dinner",
    }


@router.get("/prep/{store_id}")
async def get_prep_recommendations(
    request: Request,
    store_id: int,
    daypart: str = Query("lunch", description="Daypart to prep for"),
    settings: Settings = Depends(get_settings),
) -> List[PrepRecommendation]:
    """
    Get prep recommendations based on demand forecast.
    
    Attempts to use Databricks Model Serving for demand-aware recommendations.
    Returns suggested quantities for key items.
    Uses client's local date for forecasting.
    """
    import random

    # Daypart multipliers based on traffic patterns (dinner-forward by default)
    multiplier = {
        "lunch": 0.6,
        "afternoon": 0.4,
        "dinner": 1.0,
        "late_night": 0.4,
    }.get(daypart, 0.5)

    # Try to get model-based forecast to scale recommendations
    demand_scale = 1.0
    model_used = False
    client_now = get_client_adjusted_time(request)
    try:
        today = client_now.strftime("%Y-%m-%d")
        result = await model_client.predict_demand(
            store_id=store_id,
            date=today,
            base_transactions=200,
            base_revenue=2500.0,
        )
        predictions = result.get("predictions", [])
        if predictions and len(predictions) > 0:
            predicted_txn = int(predictions[0]) if isinstance(predictions[0], (int, float)) else 200
            # Scale recommendations based on predicted vs baseline demand
            demand_scale = predicted_txn / 200.0
            model_used = True
            logger.info(f"Prep recommendations scaled by {demand_scale:.2f}x based on ML forecast")
    except Exception as e:
        logger.warning(f"Model serving unavailable for prep recommendations, using baseline: {e}")

    # Prep items come from the taxonomy: prep subtypes (high priority) plus a few
    # ingredients (medium) — no hardcoded product names.
    base_items = [
        {"item": s["label"], "base_qty": max(10, int(60 * s["popularity"])),
         "prep_time": f"{s['prep_time_min']} min", "priority": "high"}
        for s in domain.prep_subtypes()
    ]
    for ing in domain.ingredients()[:3]:
        base_items.append({"item": ing["name"], "base_qty": int(ing.get("par", 20) or 20),
                           "prep_time": "portion", "priority": "medium"})

    return [
        PrepRecommendation(
            item=item["item"],
            quantity=int(item["base_qty"] * multiplier * demand_scale * (1.0 if model_used else random.uniform(0.9, 1.1))),
            prep_time=item["prep_time"],
            priority=item["priority"]
        )
        for item in base_items
    ]


@router.post("/predict/{store_id}")
async def predict_demand(
    store_id: int,
    date: str,
    hour: int,
    settings: Settings = Depends(get_settings),
) -> dict:
    """
    Get real-time ML prediction for a specific date/hour.
    
    Calls the model serving endpoint directly.
    """
    from services.demo_data import demo_data
    DEMO_STORES = demo_data.DEMO_STORES
    import random

    store = next((s for s in DEMO_STORES if s["store_id"] == store_id), DEMO_STORES[0])

    # Get current weather
    try:
        weather = await weather_service.get_current_weather(store["lat"], store["lng"])
        weather_temp = weather["temperature"]
        weather_condition = weather["condition"]
    except Exception:
        weather_temp = 70.0
        weather_condition = "clear"

    # Check for events
    try:
        events = await events_service.check_event_impact(store["lat"], store["lng"], date)
        is_event_day = events["has_major_event"]
    except Exception:
        is_event_day = False

    # Try to call model serving endpoint
    try:
        result = await model_client.predict_demand(
            store_id=store_id,
            date=date,
            base_transactions=200,  # Historical baseline
            base_revenue=2500.0,
        )
        # Parse and return prediction
        predictions = result.get("predictions", [])
        if predictions:
            base_txn = int(predictions[0]) if isinstance(predictions[0], (int, float)) else 200
            return {
                "store_id": store_id,
                "date": date,
                "hour": hour,
                "predicted_transactions": base_txn,
                "predicted_revenue": round(base_txn * 24.0, 2),
                "confidence": 0.88,
                "factors": {
                    "weather_temp": weather_temp,
                    "weather_condition": weather_condition,
                    "is_event_day": is_event_day,
                },
                "model_status": "active"
            }
        raise ValueError("No predictions returned")
    except Exception as e:
        # Return simulated prediction
        daypart = get_daypart(hour)
        base_txn = {"lunch": 25, "afternoon": 12, "dinner": 40, "late_night": 15}.get(daypart, 15)
        
        return {
            "store_id": store_id,
            "date": date,
            "hour": hour,
            "predicted_transactions": int(base_txn * random.uniform(0.8, 1.2)),
            "predicted_revenue": round(base_txn * 24.0 * random.uniform(0.9, 1.1), 2),
            "confidence": random.uniform(0.80, 0.92),
            "factors": {
                "weather_temp": weather_temp,
                "weather_condition": weather_condition,
                "is_event_day": is_event_day,
            },
            "model_status": "simulated"
        }


