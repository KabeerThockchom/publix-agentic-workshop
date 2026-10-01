"""
Shared Demo Data Service.

Provides consistent demo data across all API endpoints.
Uses seeded random generation based on store_id and date to ensure:
- Same sales/revenue numbers across Operations, Forecast views
- Consistent inventory levels across Inventory display and ML suggestions
- Matching % vs forecast calculations
- Stable prep inventory across the Prep Scheduler page and recommendations

This is the SINGLE SOURCE OF TRUTH for all demo data. The QSR taxonomy it uses
(ingredients, prep subtypes, stores, hours, dayparts) comes from the runtime
domain loader (config/domain.py -> config/domain.json), so re-skinning for a new
customer means editing the taxonomy, not this file.
"""

from typing import Dict, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import random
import logging

from config.domain import domain

logger = logging.getLogger(__name__)

# === Data Classes ===

@dataclass
class DailySalesData:
    """Daily sales metrics for a store."""
    date: str
    total_sales: float
    total_transactions: int
    avg_ticket: float
    vs_yesterday_pct: float
    vs_forecast_pct: float
    forecast_sales: float
    forecast_transactions: int
    
    # Hourly breakdown
    hourly_sales: Dict[int, float] = field(default_factory=dict)
    hourly_transactions: Dict[int, int] = field(default_factory=dict)
    
    # Channel breakdown
    channel_breakdown: Dict[str, float] = field(default_factory=dict)


@dataclass 
class InventoryItem:
    """Single inventory item state."""
    id: int
    name: str
    category: str
    unit: str
    par_level: float
    current_stock: float
    days_supply: float
    status: str  # "good", "low", "critical", "overstocked"
    cost_per_unit: float


@dataclass
class DoughItem:
    """Prepped-item inventory state for a single prep subtype.

    (Dataclass/field names kept for wire + Lakebase-DB compatibility; the
    `crust_type` field is the subtype's display name.)
    """
    crust_type: str
    quantity: int
    freshness_status: str  # "fresh", "aging", "expired"
    hours_until_stale: float
    last_prepped_hour: int
    popularity: float


# === Constants (sourced from the domain taxonomy: config/domain.json) ===

# Store operating window (exclusive upper bound for range()).
STORE_OPEN = domain.operating_hours()["open"]
STORE_CLOSE = domain.operating_hours()["close"]

# Ingredient catalog grouped by category — the single source of truth.
# Shape: {id, name, category, unit, par, cost_per_unit}.
INGREDIENTS = domain.ingredients()

# Prep subtypes for the Prep Scheduler surface (was crust/dough types).
# `name`/`bake_time_minutes` are kept as the demo/wire-compatible field names;
# their VALUES come from the domain subtypes (label / prep_time_min).
PREP_SUBTYPES = [
    {
        "id": s["id"],
        "name": s["label"],
        "bake_time_minutes": s["prep_time_min"],
        "freshness_hours": s["freshness_hours"],
        "popularity": s["popularity"],
    }
    for s in domain.prep_subtypes()
]


def _build_hourly_traffic_pattern() -> Dict[int, float]:
    """% of daily traffic by hour, derived from the domain dayparts.

    Each daypart's `factor` is spread evenly across its hours and normalized
    over the operating window, so the pattern adapts to any customer's hours.
    """
    pattern: Dict[int, float] = {}
    for dp in domain.dayparts():
        start = max(dp.get("start", STORE_OPEN), STORE_OPEN)
        end = min(dp.get("end", STORE_CLOSE), STORE_CLOSE)
        hours = list(range(start, end))
        if not hours:
            continue
        per_hour = dp.get("factor", 0) / len(hours)
        for h in hours:
            pattern[h] = pattern.get(h, 0) + per_hour
    total = sum(pattern.values())
    if total > 0:
        pattern = {h: v / total for h, v in pattern.items()}
    return pattern


# Hourly traffic pattern (% of daily traffic by hour), derived from dayparts.
HOURLY_TRAFFIC_PATTERN = _build_hourly_traffic_pattern()


# === Store Data Constants ===

# Store fleet — sourced from the domain taxonomy, mapped to the demo shape
# ({store_id, open_date} kept as the field names existing callers expect).
DEMO_STORES = [
    {
        "store_id": s["id"],
        "name": s["name"],
        "address": s.get("address", ""),
        "city": s.get("city", ""),
        "state": s.get("state", ""),
        "lat": s["lat"],
        "lng": s["lng"],
        "sqft": s.get("sqft", 1400),
        "open_date": s.get("opened", "2020-01-01"),
    }
    for s in domain.stores()
]


# === Cache Storage ===

# Cache structure: {cache_key: (timestamp, data)}
_sales_cache: Dict[str, tuple] = {}
_inventory_cache: Dict[str, tuple] = {}
_dough_cache: Dict[str, tuple] = {}
_store_kpis_cache: Dict[str, tuple] = {}

CACHE_TTL_SECONDS = 300  # 5 minutes


def _get_cache_key(store_id: int, date: str) -> str:
    """Generate cache key for store+date combination."""
    return f"{store_id}_{date}"


def _is_cache_valid(cache: Dict, key: str) -> bool:
    """Check if cache entry is still valid."""
    if key not in cache:
        return False
    timestamp, _ = cache[key]
    return (datetime.now() - timestamp).total_seconds() < CACHE_TTL_SECONDS


# === Sales Data Generation ===

def get_daily_sales(store_id: int, date: str, current_hour: Optional[int] = None) -> DailySalesData:
    """
    Get consistent daily sales data for a store.
    
    Uses seeded random for deterministic results within the cache period.
    """
    cache_key = _get_cache_key(store_id, date)
    
    if _is_cache_valid(_sales_cache, cache_key):
        _, data = _sales_cache[cache_key]
        return data
    
    # Generate new data with seeded random
    seed = hash(f"{store_id}_{date}") % (2**32)
    rng = random.Random(seed)
    
    # Parse date
    date_obj = datetime.strptime(date, "%Y-%m-%d")
    is_weekend = date_obj.weekday() >= 5
    
    # Base daily metrics (varies by store and day)
    store_factor = 0.8 + (store_id % 10) * 0.05  # Store performance varies 0.8-1.25x
    
    # Peaks on weekends; weekdays are lighter.
    if is_weekend:
        base_transactions = int(230 * store_factor * rng.uniform(0.9, 1.1))
    else:
        base_transactions = int(175 * store_factor * rng.uniform(0.9, 1.1))

    avg_ticket = rng.uniform(21.50, 26.50)  # average order ticket
    total_sales = base_transactions * avg_ticket
    
    # Forecast (slightly different from actual)
    forecast_transactions = int(base_transactions * rng.uniform(0.92, 1.08))
    forecast_sales = forecast_transactions * avg_ticket
    
    # Calculate % vs forecast
    vs_forecast_pct = ((total_sales - forecast_sales) / forecast_sales) * 100
    
    # Yesterday's comparison (consistent with yesterday's data)
    yesterday_seed = hash(f"{store_id}_{(date_obj - timedelta(days=1)).strftime('%Y-%m-%d')}") % (2**32)
    yesterday_rng = random.Random(yesterday_seed)
    yesterday_transactions = int(base_transactions * yesterday_rng.uniform(0.85, 1.15))
    yesterday_sales = yesterday_transactions * avg_ticket
    vs_yesterday_pct = ((total_sales - yesterday_sales) / yesterday_sales) * 100
    
    # Generate hourly breakdown
    hourly_sales = {}
    hourly_transactions = {}
    
    for hour in range(STORE_OPEN, STORE_CLOSE):
        hour_pct = HOURLY_TRAFFIC_PATTERN.get(hour, 0.05)
        hourly_transactions[hour] = int(base_transactions * hour_pct * rng.uniform(0.85, 1.15))
        hourly_sales[hour] = hourly_transactions[hour] * avg_ticket * rng.uniform(0.95, 1.05)

    # Channel breakdown (keys match domain sales_channels).
    in_store_pct = rng.uniform(0.30, 0.36)   # in-store
    delivery_pct = rng.uniform(0.38, 0.44)   # first-party delivery
    app_pct = rng.uniform(0.15, 0.20)        # mobile app / rewards
    third_party_pct = 1 - in_store_pct - delivery_pct - app_pct  # 3rd-party marketplaces
    
    channel_breakdown = {
        "in_store": in_store_pct,
        "delivery": delivery_pct,
        "app": app_pct,
        "third_party": third_party_pct,
    }
    
    data = DailySalesData(
        date=date,
        total_sales=round(total_sales, 2),
        total_transactions=base_transactions,
        avg_ticket=round(avg_ticket, 2),
        vs_yesterday_pct=round(vs_yesterday_pct, 1),
        vs_forecast_pct=round(vs_forecast_pct, 1),
        forecast_sales=round(forecast_sales, 2),
        forecast_transactions=forecast_transactions,
        hourly_sales=hourly_sales,
        hourly_transactions=hourly_transactions,
        channel_breakdown=channel_breakdown,
    )
    
    _sales_cache[cache_key] = (datetime.now(), data)
    logger.debug(f"Generated sales data for store {store_id} on {date}: ${total_sales:.2f}")
    
    return data


def get_sales_up_to_hour(store_id: int, date: str, current_hour: int) -> dict:
    """
    Get accumulated sales up to a specific hour.
    
    Used by Operations page to show "sales today" based on time of day.
    """
    daily = get_daily_sales(store_id, date, current_hour)
    
    # Sum up sales and transactions up to current hour
    sales_so_far = sum(
        daily.hourly_sales.get(h, 0)
        for h in range(STORE_OPEN, min(current_hour + 1, STORE_CLOSE))
    )
    transactions_so_far = sum(
        daily.hourly_transactions.get(h, 0)
        for h in range(STORE_OPEN, min(current_hour + 1, STORE_CLOSE))
    )
    
    return {
        "sales_today": round(sales_so_far, 2),
        "transactions_today": transactions_so_far,
        "vs_yesterday_pct": daily.vs_yesterday_pct,
        "vs_forecast_pct": daily.vs_forecast_pct,
        "current_hour_sales": daily.hourly_sales.get(current_hour, 0),
        "channel_breakdown": daily.channel_breakdown,
        "forecast_sales": daily.forecast_sales,
    }


# === Inventory Data Generation ===

def get_inventory_levels(store_id: int, date: str) -> List[InventoryItem]:
    """
    Get consistent inventory levels for a store.
    
    Same levels used for display AND ML model inputs.
    """
    cache_key = _get_cache_key(store_id, date)
    
    if _is_cache_valid(_inventory_cache, cache_key):
        _, data = _inventory_cache[cache_key]
        return data
    
    # Generate with seeded random
    seed = hash(f"inv_{store_id}_{date}") % (2**32)
    rng = random.Random(seed)
    
    inventory = []

    for ing in INGREDIENTS:
        # Generate stock level (varies 20% to 130% of par)
        stock_pct = rng.uniform(0.2, 1.3)
        current_stock = round(ing["par"] * stock_pct, 1)
        days_supply = round(current_stock / (ing["par"] / 3), 1)  # Assuming 3-day par
        
        # Determine status
        if days_supply < 1:
            status = "critical"
        elif days_supply < 2:
            status = "low"
        elif days_supply > 5:
            status = "overstocked"
        else:
            status = "good"
        
        inventory.append(InventoryItem(
            id=ing["id"],
            name=ing["name"],
            category=ing["category"],
            unit=ing["unit"],
            par_level=ing["par"],
            current_stock=current_stock,
            days_supply=days_supply,
            status=status,
            cost_per_unit=ing["cost_per_unit"],
        ))
    
    _inventory_cache[cache_key] = (datetime.now(), inventory)
    logger.debug(f"Generated inventory data for store {store_id} on {date}")
    
    return inventory


def get_inventory_summary(store_id: int, date: str) -> dict:
    """Get inventory summary stats - uses same data as get_inventory_levels."""
    inventory = get_inventory_levels(store_id, date)
    
    items_good = sum(1 for i in inventory if i.status == "good")
    items_low = sum(1 for i in inventory if i.status == "low")
    items_critical = sum(1 for i in inventory if i.status == "critical")
    items_overstocked = sum(1 for i in inventory if i.status == "overstocked")
    
    total_value = sum(i.current_stock * i.cost_per_unit for i in inventory)
    
    return {
        "total_items": len(inventory),
        "items_good": items_good,
        "items_low": items_low,
        "items_critical": items_critical,
        "items_overstocked": items_overstocked,
        "total_inventory_value": round(total_value, 2),
    }


def get_items_needing_order(store_id: int, date: str) -> List[InventoryItem]:
    """Get items that need to be ordered (low/critical) - from same data source."""
    inventory = get_inventory_levels(store_id, date)
    return [i for i in inventory if i.status in ("low", "critical") or i.days_supply < 3]


# === Dough Prep Inventory Generation ===

def get_dough_inventory(store_id: int, date: str, current_hour: int) -> List[DoughItem]:
    """
    Get consistent prepped dough-ball inventory for a store, by crust type.

    Used by the Prep Scheduler display AND recommendations.
    """
    cache_key = f"dough_{store_id}_{date}_{current_hour // 2}"  # Cache per 2-hour block

    if _is_cache_valid(_dough_cache, cache_key):
        _, data = _dough_cache[cache_key]
        return data

    # Generate with seeded random
    seed = hash(f"dough_{store_id}_{date}_{current_hour // 2}") % (2**32)
    rng = random.Random(seed)

    dough_items = []

    for crust in PREP_SUBTYPES:
        # Quantity varies by time of day (more prepped at start, depleted by end)
        span = max(1, STORE_CLOSE - STORE_OPEN)
        time_factor = max(0.1, 1.0 - (current_hour - STORE_OPEN) / span)
        base_qty = int(60 * crust["popularity"])  # Base starting dough balls prepped
        qty = max(2, int(base_qty * time_factor * rng.uniform(0.6, 1.2)))

        # When was this crust's dough last pulled & prepped? (prep pull times)
        prep_hours = [10, 14, 17, 20]
        last_prep = max([h for h in prep_hours if h <= current_hour], default=STORE_OPEN)
        hours_since_prep = current_hour - last_prep + rng.uniform(0, 0.5)

        # Dough usable window
        hours_until_stale = crust["freshness_hours"] - hours_since_prep

        if hours_until_stale < 0:
            freshness = "expired"
        elif hours_until_stale < 1:
            freshness = "aging"
        else:
            freshness = "fresh"

        dough_items.append(DoughItem(
            crust_type=crust["name"],
            quantity=qty,
            freshness_status=freshness,
            hours_until_stale=round(max(0, hours_until_stale), 1),
            last_prepped_hour=last_prep,
            popularity=crust["popularity"],
        ))

    _dough_cache[cache_key] = (datetime.now(), dough_items)
    logger.debug(f"Generated dough inventory for store {store_id} at hour {current_hour}")

    return dough_items


# === Helper Functions ===

def clear_cache():
    """Clear all cached data (useful for testing)."""
    global _sales_cache, _inventory_cache, _dough_cache, _store_kpis_cache
    _sales_cache = {}
    _inventory_cache = {}
    _dough_cache = {}
    _store_kpis_cache = {}
    logger.info("Demo data cache cleared")


def get_forecast_for_date(store_id: int, date: str) -> dict:
    """Get forecast data - consistent with actual sales."""
    sales = get_daily_sales(store_id, date)
    return {
        "predicted_transactions": sales.forecast_transactions,
        "predicted_revenue": sales.forecast_sales,
        "actual_transactions": sales.total_transactions,
        "actual_revenue": sales.total_sales,
        "vs_forecast_pct": sales.vs_forecast_pct,
    }


# === Store KPI Data Generation (Regional Manager Views) ===

@dataclass
class StoreKPI:
    """KPI data for a single store."""
    store_id: int
    name: str
    city: str
    address: str
    latitude: float
    longitude: float
    sqft: int
    open_date: str
    sales_today: float
    sales_wtd: float
    sales_mtd: float
    sales_ytd: float
    vs_forecast_pct: float
    labor_cost_pct: float
    rank: int
    trend: str  # "up", "down", "flat"
    staff_count: int
    manager_name: str
    phone: str


def get_all_store_kpis(date: str) -> List[StoreKPI]:
    """
    Get consistent KPI data for all stores.
    
    Uses seeded random based on date to ensure all stores have
    consistent data throughout the day.
    """
    cache_key = f"store_kpis_{date}"
    
    if _is_cache_valid(_store_kpis_cache, cache_key):
        _, data = _store_kpis_cache[cache_key]
        return data
    
    # Generate with seeded random for entire region
    seed = hash(f"region_kpis_{date}") % (2**32)
    rng = random.Random(seed)
    
    store_kpis = []
    
    # First, generate raw metrics for all stores
    raw_metrics = []
    for store in DEMO_STORES:
        store_id = store["store_id"]
        
        # Store-specific seed for consistent individual store data
        store_seed = hash(f"store_{store_id}_{date}") % (2**32)
        store_rng = random.Random(store_seed)
        
        # Base performance varies by store (some stores perform better)
        # Using sqft as a factor (larger stores = more sales potential)
        sqft = store.get("sqft", 1600)
        size_factor = sqft / 1600  # Normalize to avg sqft
        
        # Performance factor (deterministic per store)
        perf_factor = 0.7 + (store_id % 10) * 0.06  # 0.7 to 1.24
        
        # Daily sales
        base_daily = 4200 * size_factor * perf_factor
        sales_today = base_daily * store_rng.uniform(0.85, 1.15)
        
        # Weekly (5 days worth roughly)
        sales_wtd = sales_today * store_rng.uniform(4.5, 5.5)
        
        # Monthly
        sales_mtd = sales_today * store_rng.uniform(18, 22)
        
        # Yearly
        sales_ytd = sales_mtd * store_rng.uniform(10, 12)
        
        # Forecast comparison (consistent with individual store data)
        daily_data = get_daily_sales(store_id, date)
        vs_forecast_pct = daily_data.vs_forecast_pct
        
        # Labor cost (varies by store efficiency)
        labor_cost_pct = store_rng.uniform(22, 32)
        
        # Trend based on yesterday comparison
        vs_yesterday = daily_data.vs_yesterday_pct
        if vs_yesterday > 3:
            trend = "up"
        elif vs_yesterday < -3:
            trend = "down"
        else:
            trend = "flat"
        
        # Staff count (based on store size)
        staff_count = int(sqft / 300) + store_rng.randint(0, 2)
        
        raw_metrics.append({
            "store": store,
            "sales_today": sales_today,
            "sales_wtd": sales_wtd,
            "sales_mtd": sales_mtd,
            "sales_ytd": sales_ytd,
            "vs_forecast_pct": vs_forecast_pct,
            "labor_cost_pct": labor_cost_pct,
            "trend": trend,
            "staff_count": staff_count,
        })
    
    # Sort by monthly sales to determine rank
    raw_metrics.sort(key=lambda x: x["sales_mtd"], reverse=True)
    
    # Build final KPI objects with ranks
    for rank, metrics in enumerate(raw_metrics, 1):
        store = metrics["store"]
        store_id = store["store_id"]
        
        store_kpis.append(StoreKPI(
            store_id=store_id,
            name=store["name"],
            city=store["city"],
            address=store["address"],
            latitude=store["lat"],
            longitude=store["lng"],
            sqft=store.get("sqft", 1600),
            open_date=store.get("open_date", "2020-01-01"),
            sales_today=round(metrics["sales_today"], 2),
            sales_wtd=round(metrics["sales_wtd"], 2),
            sales_mtd=round(metrics["sales_mtd"], 2),
            sales_ytd=round(metrics["sales_ytd"], 2),
            vs_forecast_pct=round(metrics["vs_forecast_pct"], 1),
            labor_cost_pct=round(metrics["labor_cost_pct"], 1),
            rank=rank,
            trend=metrics["trend"],
            staff_count=metrics["staff_count"],
            manager_name=f"Manager {store_id}",
            phone=f"(408) 555-{1000 + store_id:04d}",
        ))
    
    # Sort by store_id for consistent ordering
    store_kpis.sort(key=lambda x: x.store_id)
    
    _store_kpis_cache[cache_key] = (datetime.now(), store_kpis)
    logger.debug(f"Generated KPIs for {len(store_kpis)} stores on {date}")
    
    return store_kpis


def get_store_kpi(store_id: int, date: str) -> Optional[StoreKPI]:
    """Get KPI for a single store - consistent with get_all_store_kpis."""
    all_kpis = get_all_store_kpis(date)
    return next((k for k in all_kpis if k.store_id == store_id), None)


def get_store_rankings(date: str) -> List[StoreKPI]:
    """Get stores sorted by rank (best performers first)."""
    all_kpis = get_all_store_kpis(date)
    return sorted(all_kpis, key=lambda x: x.rank)


# Singleton-style accessor for consistency
demo_data = type('DemoDataService', (), {
    'get_daily_sales': staticmethod(get_daily_sales),
    'get_sales_up_to_hour': staticmethod(get_sales_up_to_hour),
    'get_inventory_levels': staticmethod(get_inventory_levels),
    'get_inventory_summary': staticmethod(get_inventory_summary),
    'get_items_needing_order': staticmethod(get_items_needing_order),
    'get_dough_inventory': staticmethod(get_dough_inventory),
    'get_forecast_for_date': staticmethod(get_forecast_for_date),
    'get_all_store_kpis': staticmethod(get_all_store_kpis),
    'get_store_kpi': staticmethod(get_store_kpi),
    'get_store_rankings': staticmethod(get_store_rankings),
    'clear_cache': staticmethod(clear_cache),
    'INGREDIENTS': INGREDIENTS,
    'PREP_SUBTYPES': PREP_SUBTYPES,
    'HOURLY_TRAFFIC_PATTERN': HOURLY_TRAFFIC_PATTERN,
    'DEMO_STORES': DEMO_STORES,
    'STORE_OPEN': STORE_OPEN,
    'STORE_CLOSE': STORE_CLOSE,
})()

