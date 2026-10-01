"""
Store data API endpoints.

Provides store metadata, locations, and KPIs for both personas:
- Store Manager: Single store details
- Regional Manager: All stores for map and comparison views

Uses shared demo_data service for consistent KPIs across all views.
"""

from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, Query, HTTPException, Request
from pydantic import BaseModel
from config.settings import Settings, get_settings
from config.database import query_sql
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


def get_client_adjusted_time(request: Request) -> datetime:
    """Get current time adjusted to client's local timezone using X-Client-Local-Hour header."""
    from datetime import timedelta
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

class StoreLocation(BaseModel):
    """Store location and coordinates."""
    store_id: int
    name: str
    address: str
    city: str
    latitude: float
    longitude: float


class StoreKPIs(BaseModel):
    """Store key performance indicators."""
    store_id: int
    name: str
    city: Optional[str] = None
    sales_today: float
    sales_wtd: float
    sales_mtd: float
    sales_ytd: float
    vs_forecast_pct: float
    labor_cost_pct: float
    rank: int
    trend: str  # "up", "down", "flat"


class StoreDetail(BaseModel):
    """Full store details."""
    store_id: int
    name: str
    address: str
    city: str
    latitude: float
    longitude: float
    manager_name: str
    phone: str
    sqft: int
    open_date: str
    sales_today: float
    sales_ytd: float
    vs_forecast_pct: float
    labor_cost_pct: float
    rank: int
    staff_count: int


class StoresResponse(BaseModel):
    """Response for list of stores."""
    stores: List[StoreKPIs]
    total: int


# === Endpoints ===
# Note: DEMO_STORES is now in services/demo_data.py as the single source of truth

@router.get("/", response_model=StoresResponse)
async def get_all_stores(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> StoresResponse:
    """
    Get all stores with KPIs.
    
    Uses shared demo_data service for consistent KPIs.
    Used by Regional Manager for map and comparison views.
    """
    from services.demo_data import demo_data
    
    client_now = get_client_adjusted_time(request)
    date_str = client_now.strftime("%Y-%m-%d")
    
    warehouse_id = settings.databricks_warehouse_id
    
    if warehouse_id:
        try:
            # Query from Delta table
            # Reads the materialized view mv_store_overview (fast) rather than
            # the underlying stores_kpi_view. The MV exposes store_name and
            # vs_yesterday_pct; alias them to the API's name/vs_forecast_pct.
            query = f"""
                SELECT
                    store_id, store_name AS name, city,
                    sales_today, sales_wtd, sales_mtd, sales_ytd,
                    vs_yesterday_pct AS vs_forecast_pct, labor_cost_pct, rank,
                    CASE
                        WHEN vs_yesterday_pct > 2 THEN 'up'
                        WHEN vs_yesterday_pct < -2 THEN 'down'
                        ELSE 'flat'
                    END as trend
                FROM {settings.get_table_path('mv_store_overview')}
                ORDER BY rank
            """
            results = query_sql(query, warehouse_id)
            
            stores = [StoreKPIs(**row) for row in results]
            return StoresResponse(stores=stores, total=len(stores))
            
        except Exception as e:
            logger.warning(f"Could not fetch stores from SQL Warehouse, using demo data: {e}")

    # Return consistent demo data from shared service
    all_kpis = demo_data.get_all_store_kpis(date_str)
    
    stores = []
    for kpi in all_kpis:
        stores.append(StoreKPIs(
            store_id=kpi.store_id,
            name=kpi.name,
            city=getattr(kpi, "city", None),
            sales_today=kpi.sales_today,
            sales_wtd=kpi.sales_wtd,
            sales_mtd=kpi.sales_mtd,
            sales_ytd=kpi.sales_ytd,
            vs_forecast_pct=kpi.vs_forecast_pct,
            labor_cost_pct=kpi.labor_cost_pct,
            rank=kpi.rank,
            trend=kpi.trend,
        ))
    
    return StoresResponse(stores=stores, total=len(stores))


@router.get("/locations")
async def get_store_locations() -> List[StoreLocation]:
    """
    Get all store locations for map display.
    
    Uses shared DEMO_STORES from demo_data service.
    Returns coordinates and basic info for Deck.gl visualization.
    """
    from services.demo_data import demo_data
    
    return [
        StoreLocation(
            store_id=s["store_id"],
            name=s["name"],
            address=s["address"],
            city=s["city"],
            latitude=s["lat"],
            longitude=s["lng"],
        )
        for s in demo_data.DEMO_STORES
    ]


@router.get("/{store_id}")
async def get_store_detail(
    request: Request,
    store_id: int,
    settings: Settings = Depends(get_settings),
) -> StoreDetail:
    """
    Get detailed information for a single store.
    
    Uses shared demo_data service for consistent KPIs.
    Used by Store Manager view and drill-down from map.
    Queries both 'stores' table for store details and 'stores_kpi_view' for performance.
    """
    from services.demo_data import demo_data
    
    client_now = get_client_adjusted_time(request)
    date_str = client_now.strftime("%Y-%m-%d")
    
    # Get consistent KPI from shared service
    store_kpi = demo_data.get_store_kpi(store_id, date_str)
    
    if not store_kpi:
        raise HTTPException(status_code=404, detail=f"Store {store_id} not found")

    warehouse_id = settings.databricks_warehouse_id
    
    if warehouse_id:
        try:
            # Try to fetch from stores table first
            stores_query = f"""
                SELECT * FROM {settings.get_table_path('stores')}
                WHERE store_id = {store_id}
            """
            store_results = query_sql(stores_query, warehouse_id)
            
            # Also fetch from the materialized view for performance data
            kpi_query = f"""
                SELECT
                    store_id, store_name AS name, city,
                    sales_today, sales_wtd, sales_mtd, sales_ytd,
                    vs_yesterday_pct AS vs_forecast_pct, labor_cost_pct, rank
                FROM {settings.get_table_path('mv_store_overview')}
                WHERE store_id = {store_id}
            """
            kpi_results = query_sql(kpi_query, warehouse_id)
            
            if store_results:
                # Merge KPI data if available
                store_info = store_results[0]
                if kpi_results:
                    store_info.update(kpi_results[0])
                return StoreDetail(**store_info)
        except Exception as e:
            logger.warning(f"Could not fetch store {store_id} from SQL Warehouse, using demo data: {e}")

    # Return consistent demo data from shared service
    return StoreDetail(
        store_id=store_kpi.store_id,
        name=store_kpi.name,
        address=store_kpi.address,
        city=store_kpi.city,
        latitude=store_kpi.latitude,
        longitude=store_kpi.longitude,
        manager_name=store_kpi.manager_name,
        phone=store_kpi.phone,
        sqft=store_kpi.sqft,
        open_date=store_kpi.open_date,
        sales_today=store_kpi.sales_today,
        sales_ytd=store_kpi.sales_ytd,
        vs_forecast_pct=store_kpi.vs_forecast_pct,
        labor_cost_pct=store_kpi.labor_cost_pct,
        rank=store_kpi.rank,
        staff_count=store_kpi.staff_count,
    )


@router.get("/{store_id}/rankings")
async def get_store_rankings(
    request: Request,
    store_id: int,
    settings: Settings = Depends(get_settings),
) -> dict:
    """
    Get store's ranking vs peers.
    
    Uses shared demo_data service for consistent rankings.
    Returns ranking in various categories.
    """
    from services.demo_data import demo_data
    import random
    
    client_now = get_client_adjusted_time(request)
    date_str = client_now.strftime("%Y-%m-%d")
    
    # Get consistent KPI from shared service
    store_kpi = demo_data.get_store_kpi(store_id, date_str)
    
    if not store_kpi:
        raise HTTPException(status_code=404, detail=f"Store {store_id} not found")
    
    # Use seeded random for consistent sub-rankings
    seed = hash(f"rankings_{store_id}_{date_str}") % (2**32)
    rng = random.Random(seed)
    
    # Overall rank comes from shared KPI (based on sales)
    overall_rank = store_kpi.rank

    # Total store count is driven by the configured fleet (domain-generated),
    # not a hardcoded number — a customer may have any number of stores.
    total_stores = len(demo_data.DEMO_STORES)

    # Generate consistent sub-rankings based on overall rank
    # Better overall performers tend to be better in all categories
    base_variance = 5  # How much categories can vary from overall

    def _bounded(r: int) -> int:
        return max(1, min(total_stores, r + rng.randint(-base_variance, base_variance)))

    return {
        "store_id": store_id,
        "overall_rank": overall_rank,
        "total_stores": total_stores,
        "rankings": {
            "sales": overall_rank,  # Same as overall (based on sales)
            "labor_efficiency": _bounded(overall_rank),
            "customer_satisfaction": _bounded(overall_rank),
            "inventory_accuracy": _bounded(overall_rank),
        },
        "percentile": max(5, min(99, round(100 - (overall_rank / max(1, total_stores)) * 100) + rng.randint(-5, 5))),
    }


