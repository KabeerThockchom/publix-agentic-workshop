"""
Inventory Management API endpoints.

Provides ingredient tracking and ML-powered predictions:
- Current stock levels by ingredient
- Deliveries in transit
- Suggested order quantities
- Waste tracking

Uses the inventory-predictor model serving endpoint.
Ingredient catalog is sourced from services/demo_data.py (the domain taxonomy).
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


# === Pydantic Models ===

class Ingredient(BaseModel):
    """Single ingredient stock level."""
    id: int
    name: str
    category: str  # an ingredient category key from domain.yaml (ingredient_categories)
    unit: str  # "lbs", "units", "oz"
    current_stock: float
    par_level: float  # Target stock level
    days_supply: float
    status: str  # "good", "low", "critical", "overstocked"


class Delivery(BaseModel):
    """Incoming delivery."""
    id: int
    supplier: str
    expected_date: str
    expected_time: str
    status: str  # "scheduled", "in_transit", "delivered"
    items: List[dict]  # [{"name": "Lettuce", "quantity": 20}]


class OrderSuggestion(BaseModel):
    """ML-suggested order quantity."""
    ingredient_id: int
    ingredient_name: str
    current_stock: float
    suggested_quantity: float
    urgency: str  # "low", "medium", "high", "critical"
    reason: str
    estimated_cost: float


class InventorySummary(BaseModel):
    """Inventory summary for a store."""
    store_id: int
    timestamp: str
    total_items: int
    items_low: int
    items_critical: int
    items_good: int
    next_delivery: Optional[Delivery]
    total_inventory_value: float


# Ingredient catalog is the single source of truth in services/demo_data.py (INGREDIENTS).


# === Endpoints ===

@router.get("/summary/{store_id}")
async def get_inventory_summary(
    request: Request,
    store_id: int,
    settings: Settings = Depends(get_settings),
) -> InventorySummary:
    """
    Get inventory summary for a store.
    
    Uses shared demo_data service for consistent inventory levels.
    Returns overview of stock levels and upcoming deliveries.
    Uses client's local time for timestamps.
    """
    from services.demo_data import demo_data

    now = get_client_adjusted_time(request)
    date_str = now.strftime("%Y-%m-%d")

    # Get consistent inventory summary from shared service
    summary = demo_data.get_inventory_summary(store_id, date_str)

    # Next delivery
    next_delivery = Delivery(
        id=1001,
        supplier=domain.supplier_name(),
        expected_date=(now + timedelta(days=1)).strftime("%Y-%m-%d"),
        expected_time="06:00 AM",
        status="scheduled",
        items=[
            {"name": n, "quantity": q}
            for n, q in zip([i["name"] for i in domain.ingredients()[:3]], [120, 40, 25])
        ]
    )

    return InventorySummary(
        store_id=store_id,
        timestamp=now.isoformat(),
        total_items=summary["total_items"],
        items_low=summary["items_low"],
        items_critical=summary["items_critical"],
        items_good=summary["items_good"],
        next_delivery=next_delivery,
        total_inventory_value=summary["total_inventory_value"]
    )


@router.get("/levels/{store_id}")
async def get_inventory_levels(
    request: Request,
    store_id: int,
    category: Optional[str] = Query(None, description="Filter by category"),
    settings: Settings = Depends(get_settings),
) -> List[Ingredient]:
    """
    Get current inventory levels for all ingredients.
    
    Uses shared demo_data service for consistent levels.
    Optionally filter by category.
    """
    from services.demo_data import demo_data

    now = get_client_adjusted_time(request)
    date_str = now.strftime("%Y-%m-%d")

    # Get consistent inventory from shared service
    all_inventory = demo_data.get_inventory_levels(store_id, date_str)

    ingredients = []
    for inv in all_inventory:
        if category and inv.category != category:
            continue

        ingredients.append(Ingredient(
            id=inv.id,
            name=inv.name,
            category=inv.category,
            unit=inv.unit,
            current_stock=inv.current_stock,
            par_level=inv.par_level,
            days_supply=inv.days_supply,
            status=inv.status
        ))

    return ingredients


@router.get("/deliveries/{store_id}")
async def get_deliveries(
    request: Request,
    store_id: int,
    settings: Settings = Depends(get_settings),
) -> List[Delivery]:
    """
    Get upcoming and recent deliveries for a store.
    Uses client's local time for delivery date calculations.
    """
    now = get_client_adjusted_time(request)

    deliveries = [
        Delivery(
            id=1001,
            supplier=domain.supplier_name(),
            expected_date=(now + timedelta(days=1)).strftime("%Y-%m-%d"),
            expected_time="06:00 AM",
            status="scheduled",
            items=[
                {"name": n, "quantity": q}
                for n, q in zip([i["name"] for i in domain.ingredients()[:4]], [120, 40, 25, 18])
            ]
        ),
        Delivery(
            id=1002,
            supplier="Sysco Foods",
            expected_date=(now + timedelta(days=2)).strftime("%Y-%m-%d"),
            expected_time="07:00 AM",
            status="scheduled",
            items=[
                {"name": n, "quantity": q}
                for n, q in zip([i["name"] for i in domain.ingredients()[-3:]], [300, 200, 120])
            ]
        ),
        Delivery(
            id=1000,
            supplier=domain.supplier_name(),
            expected_date=(now - timedelta(days=1)).strftime("%Y-%m-%d"),
            expected_time="06:15 AM",
            status="delivered",
            items=[
                {"name": n, "quantity": q}
                for n, q in zip(
                    [i["name"] for i in domain.ingredients() if i["category"] in ("veggie", "sauce")][:2]
                    or [i["name"] for i in domain.ingredients()[3:5]], [35, 20])
            ]
        ),
    ]

    return deliveries


@router.get("/suggestions/{store_id}")
async def get_order_suggestions(
    request: Request,
    store_id: int,
    settings: Settings = Depends(get_settings),
) -> List[OrderSuggestion]:
    """
    Get ML-suggested order quantities.
    
    Uses shared demo_data service for SAME inventory levels shown in display.
    Attempts to call the Databricks Model Serving endpoint.
    Analyzes current stock, forecast, and usage patterns.
    """
    from services.demo_data import demo_data

    now = get_client_adjusted_time(request)
    date_str = now.strftime("%Y-%m-%d")

    suggestions = []

    # Get items needing order from shared data (SAME as display)
    items_needing_order = demo_data.get_items_needing_order(store_id, date_str)

    for inv in items_needing_order:
        stock = inv.current_stock
        days_supply = inv.days_supply
        par = inv.par_level
        cost_per_unit = inv.cost_per_unit

        # Try calling the model serving endpoint
        try:
            result = await model_client.predict_inventory(
                store_id=store_id,
                ingredient_id=inv.id,
                current_stock=stock,
                par_level=float(par),
                category=inv.category,
                cost_per_unit=float(cost_per_unit),
            )
            
            # Model returns suggested_order_qty as a single prediction value
            predictions = result.get("predictions", [])
            if predictions and len(predictions) > 0:
                suggested = float(predictions[0]) if isinstance(predictions[0], (int, float)) else par - stock + (par * 0.2)
                suggested = max(0, suggested)  # Can't order negative
                # Determine urgency based on days supply
                if days_supply < 1:
                    urgency = "critical"
                elif days_supply < 2:
                    urgency = "high"
                else:
                    urgency = "medium"
                logger.info(f"Inventory model prediction for {inv.name}: order {suggested:.1f} units")
        except Exception as e:
            logger.warning(f"Inventory model unavailable for {inv.name}, using fallback: {e}")
            # Fallback calculation
            suggested = par - stock + (par * 0.2)  # Order to par + 20% buffer
            
            if days_supply < 1:
                urgency = "critical"
            elif days_supply < 2:
                urgency = "high"
            else:
                urgency = "medium"

        # Build reason based on urgency
        if urgency == "critical":
            reason = f"Only {days_supply:.1f} days supply remaining - urgent reorder needed"
        elif urgency == "high":
            reason = f"Low stock alert - {days_supply:.1f} days supply"
        else:
            reason = f"Approaching reorder point - {days_supply:.1f} days supply"

        suggestions.append(OrderSuggestion(
            ingredient_id=inv.id,
            ingredient_name=inv.name,
            current_stock=round(stock, 1),
            suggested_quantity=round(suggested, 1),
            urgency=urgency,
            reason=reason,
            estimated_cost=round(suggested * cost_per_unit, 2)
        ))

    # Sort by urgency
    urgency_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    suggestions.sort(key=lambda x: urgency_order.get(x.urgency, 4))

    return suggestions[:15]  # Return top 15 suggestions


@router.get("/waste/{store_id}")
async def get_waste_tracking(
    request: Request,
    store_id: int,
    days: int = Query(7, description="Number of days to look back"),
    settings: Settings = Depends(get_settings),
) -> dict:
    """
    Get waste tracking data for a store.
    
    Shows waste by category and trends.
    Uses client's local time for date calculations.
    """
    import random

    now = get_client_adjusted_time(request)
    
    daily_waste = []
    for i in range(days):
        date = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        daily_waste.append({
            "date": date,
            "total_waste_lbs": round(random.uniform(2, 8), 1),
            "waste_cost": round(random.uniform(15, 60), 2),
            "top_wasted": random.choice([i["name"] for i in domain.ingredients()[:6]] or ["Inventory item"])
        })

    # Category breakdown
    categories = {
        "dough": round(random.uniform(25, 40), 1),
        "cheese": round(random.uniform(20, 35), 1),
        "veggie": round(random.uniform(15, 25), 1),
        "meat": round(random.uniform(10, 20), 1),
    }

    return {
        "store_id": store_id,
        "period_days": days,
        "total_waste_lbs": sum(d["total_waste_lbs"] for d in daily_waste),
        "total_waste_cost": sum(d["waste_cost"] for d in daily_waste),
        "daily_breakdown": daily_waste,
        "category_breakdown_pct": categories,
        "trend": random.choice(["improving", "stable", "worsening"]),
        "vs_target_pct": random.uniform(-20, 30),
    }


@router.post("/predict/{store_id}")
async def predict_inventory_needs(
    store_id: int,
    ingredient_id: int,
    settings: Settings = Depends(get_settings),
) -> dict:
    """
    Get ML prediction for a specific ingredient.
    
    Calls the inventory predictor model serving endpoint.
    """
    import random
    from services.demo_data import demo_data

    # Find ingredient (single source of truth in demo_data)
    ing = next((i for i in demo_data.INGREDIENTS if i["id"] == ingredient_id), None)
    if not ing:
        return {"error": "Ingredient not found"}

    current_stock = ing["par"] * random.uniform(0.3, 0.7)

    try:
        # Try model serving endpoint (async)
        result = await model_client.predict_inventory(
            store_id=store_id,
            ingredient_id=ingredient_id,
            current_stock=current_stock,
            par_level=float(ing["par"]),
            category=ing["category"],
            cost_per_unit=float(ing["cost_per_unit"]),
        )
        # Parse model response
        predictions = result.get("predictions", [])
        if predictions:
            suggested = float(predictions[0]) if isinstance(predictions[0], (int, float)) else ing["par"] - current_stock
            days_until_stockout = current_stock / (ing["par"] / 3)
            return {
                "store_id": store_id,
                "ingredient_id": ingredient_id,
                "ingredient_name": ing["name"],
                "current_stock": round(current_stock, 1),
                "days_until_stockout": round(days_until_stockout, 1),
                "suggested_order_qty": round(max(0, suggested), 1),
                "reorder_urgency": "high" if days_until_stockout < 2 else "medium" if days_until_stockout < 4 else "low",
                "model_status": "active"
            }
        raise ValueError("No predictions returned")
    except Exception:
        # Return simulated prediction
        days_until_stockout = current_stock / (ing["par"] / 3)
        
        return {
            "store_id": store_id,
            "ingredient_id": ingredient_id,
            "ingredient_name": ing["name"],
            "current_stock": round(current_stock, 1),
            "days_until_stockout": round(days_until_stockout, 1),
            "suggested_order_qty": round(ing["par"] - current_stock + ing["par"] * 0.2, 1),
            "reorder_urgency": "high" if days_until_stockout < 2 else "medium" if days_until_stockout < 4 else "low",
            "model_status": "simulated"
        }


