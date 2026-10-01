"""
API Routes for StoreSight IQ

Organized by feature area:
- /api/stores - Store data and metadata
- /api/operations - Real-time streaming operations
- /api/forecast - Demand forecasting
- /api/labor - Labor optimization
- /api/inventory - Inventory tracking
- /api/prep - Prep Scheduler (configurable production-prep vertical)
- /api/genie - AI chatbot (Genie API)
"""

from fastapi import APIRouter

from api.stores import router as stores_router
from api.operations import router as operations_router
from api.forecast import router as forecast_router
from api.labor import router as labor_router
from api.inventory import router as inventory_router
from api.prep import router as prep_router
from api.genie import router as genie_router
from api.state import router as state_router

# Main API router
api_router = APIRouter()

# Include all feature routers
api_router.include_router(stores_router, prefix="/stores", tags=["Stores"])
api_router.include_router(operations_router, prefix="/operations", tags=["Operations"])
api_router.include_router(forecast_router, prefix="/forecast", tags=["Forecast"])
api_router.include_router(labor_router, prefix="/labor", tags=["Labor"])
api_router.include_router(inventory_router, prefix="/inventory", tags=["Inventory"])
api_router.include_router(prep_router, prefix="/prep", tags=["Prep Scheduler"])
api_router.include_router(genie_router, prefix="/genie", tags=["AI Insights"])
api_router.include_router(state_router, prefix="/state", tags=["State Persistence"])

__all__ = ["api_router"]





