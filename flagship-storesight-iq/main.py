"""
StoreSight IQ - QSR Store Operations Platform
Main FastAPI Application

A Databricks App for store operations management featuring:
- Real-time streaming operations data
- ML-powered demand forecasting
- Labor optimization
- Inventory management
- Prep schedule optimization (configurable production-prep vertical)
- AI-powered insights via Genie

Docs: https://docs.databricks.com/aws/en/dev-tools/databricks-apps/
"""

import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Any, Dict

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from config.database import (
    check_database_exists,
    database_health,
    init_engine,
    start_token_refresh,
    stop_token_refresh,
    close_connections,
    get_sql_connection,
    query_sql,
)
from config.settings import settings
from api import api_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def check_database_health_loop(interval: int):
    """Background task to periodically check database health."""
    while True:
        try:
            is_healthy = await database_health()
            if not is_healthy:
                logger.warning("Database health check failed")
        except Exception as e:
            logger.error(f"Health check exception: {e}")
        await asyncio.sleep(interval)


async def prewarm_sql_connection():
    """
    Pre-warm SQL warehouse connection on startup.
    
    This runs in a background task to avoid blocking startup,
    but ensures the slow initial connection happens before user requests.
    """
    warehouse_id = settings.databricks_warehouse_id
    if not warehouse_id:
        logger.info("SQL Warehouse not configured - skipping pre-warm")
        return
    
    try:
        logger.info("Pre-warming Databricks SQL Warehouse connection...")
        # This will trigger the initial connection and feature-flags check
        # in the background, not blocking the first user request
        conn = get_sql_connection(warehouse_id)
        
        # Run a simple query to fully initialize the connection
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchall()
        
        logger.info("✓ Databricks SQL Warehouse connection pre-warmed")
    except Exception as e:
        logger.warning(f"Databricks SQL Warehouse pre-warm failed (will retry on first request): {e}")


async def prewarm_model_serving_endpoints():
    """
    Pre-warm all Databricks Model Serving endpoints on startup.
    
    Makes lightweight test calls to each endpoint to ensure they are warmed
    and ready for user requests.
    """
    from services.model_serving import model_client
    from datetime import datetime
    
    # Endpoint names come from settings (env-driven; set by the generator/DAB).
    endpoints_to_warm = [
        ("demand_forecast", settings.demand_forecast_endpoint),
        ("labor_optimizer", settings.labor_optimizer_endpoint),
        ("inventory_predictor", settings.inventory_predictor_endpoint),
        ("prep_scheduler", settings.prep_scheduler_endpoint),
    ]
    
    logger.info("Pre-warming Databricks Model Serving endpoints...")
    
    for name, endpoint_name in endpoints_to_warm:
        try:
            # Check endpoint health first
            health = await model_client.check_endpoint_health(endpoint_name)
            if health.get("ready"):
                logger.info(f"  ✓ {name} endpoint ready")
            else:
                logger.warning(f"  ✗ {name} endpoint not ready: {health.get('state', 'UNKNOWN')}")
        except Exception as e:
            logger.warning(f"  ✗ {name} endpoint warm-up check failed: {e}")
    
    # Also make a test prediction to fully warm the endpoints
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        await model_client.predict_demand(
            store_id=1,
            date=today,
            base_transactions=200,
            base_revenue=2500.0,
        )
        logger.info("  ✓ Demand forecast model warmed with test prediction")
    except Exception as e:
        logger.debug(f"  Demand forecast test prediction skipped: {e}")
    
    logger.info("✓ Databricks Model Serving endpoints warm-up complete")


async def prewarm_genie_space():
    """
    Pre-warm Genie Space connection on startup.
    
    Initializes the Genie API client to reduce first-query latency.
    """
    from services.genie import genie_client
    
    genie_space_id = settings.genie_space_id
    if not genie_space_id:
        logger.info("Databricks Genie Space not configured - skipping pre-warm")
        return
    
    try:
        logger.info("Pre-warming Databricks Genie Space...")
        # Initialize the workspace client (lazy init happens on first access)
        _ = genie_client.client
        logger.info(f"  ✓ Genie Space {genie_space_id[:8]}... initialized")
        logger.info("✓ Databricks Genie Space pre-warmed")
    except Exception as e:
        logger.warning(f"Databricks Genie Space pre-warm failed (will retry on first request): {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    
    Handles startup and shutdown events:
    - Initialize Lakebase connection with token refresh
    - Pre-warm SQL Warehouse connection
    - Start health monitoring
    - Clean up on shutdown
    """
    logger.info("=" * 50)
    logger.info("StoreSight IQ - Starting up")
    logger.info("=" * 50)
    
    # Log Databricks configuration for debugging
    logger.info(f"DATABRICKS_HOST: {os.environ.get('DATABRICKS_HOST', 'NOT SET (will use SDK auto-detection)')}")
    logger.info(f"DEMAND_FORECAST_ENDPOINT: {os.environ.get('DEMAND_FORECAST_ENDPOINT', settings.demand_forecast_endpoint)}")
    logger.info("Model serving will use WorkspaceClient SDK (auto-authenticates in Databricks Apps)")

    # Check if Lakebase is configured and exists
    lakebase_available = check_database_exists()
    health_check_task = None

    if lakebase_available:
        try:
            init_engine()
            await start_token_refresh()
            health_check_task = asyncio.create_task(check_database_health_loop(300))
            logger.info("✓ Lakebase connection initialized")
        except Exception as e:
            logger.error(f"✗ Lakebase initialization failed: {e}")
            logger.info("  App will run without Lakebase (real-time features limited)")
    else:
        logger.info("✗ Lakebase not configured - real-time features disabled")
        logger.info("  Run notebook 01_generate_data_and_streaming.py first")

    # Pre-warm SQL Warehouse connection in background
    # This avoids the ~35 second delay on first user request
    prewarm_sql_task = asyncio.create_task(prewarm_sql_connection())
    
    # Pre-warm Model Serving endpoints in background
    prewarm_model_task = asyncio.create_task(prewarm_model_serving_endpoints())
    
    # Pre-warm Genie Space in background
    prewarm_genie_task = asyncio.create_task(prewarm_genie_space())

    logger.info("✓ Application startup complete (pre-warming services in background)")
    logger.info("=" * 50)

    yield

    # Shutdown
    logger.info("StoreSight IQ - Shutting down")
    
    # Cancel background tasks
    if health_check_task:
        health_check_task.cancel()
        try:
            await health_check_task
        except asyncio.CancelledError:
            pass
    
    # Cancel all pre-warm tasks
    for task in [prewarm_sql_task, prewarm_model_task, prewarm_genie_task]:
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
    
    await stop_token_refresh()
    close_connections()
    logger.info("Application shutdown complete")


# Create FastAPI application
app = FastAPI(
    title="StoreSight IQ",
    description="QSR Store Operations Platform powered by Databricks",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# CORS middleware for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite dev server
        "http://localhost:3000",  # Alternative React port
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Performance monitoring middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Add X-Process-Time header to all responses."""
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = f"{process_time:.3f}"
    
    # Log slow requests
    if process_time > 1.0:
        logger.warning(
            f"Slow request: {request.method} {request.url.path} - {process_time * 1000:.1f}ms"
        )
    return response


# Include API routers
app.include_router(api_router, prefix="/api")


# Root endpoint
@app.get("/")
async def root() -> Dict[str, str]:
    """Root endpoint - returns app info or serves frontend."""
    # Check if frontend build exists
    frontend_path = os.path.join(os.path.dirname(__file__), "frontend", "dist", "index.html")
    if os.path.exists(frontend_path):
        return FileResponse(frontend_path)
    
    return {
        "app": "StoreSight IQ",
        "description": "QSR Store Operations Platform",
        "version": "1.0.0",
        "docs": "/api/docs",
        "health": "/api/health",
    }


# Health check endpoint
@app.get("/api/health")
async def health_check() -> Dict[str, Any]:
    """
    Health check endpoint for monitoring.
    
    Returns status of all connected services.
    """
    # Prefer the asyncpg pool used by the state API (works with project-based
    # Lakebase via injected PG* vars + OAuth token). Fall back to the legacy
    # SQLAlchemy engine health check if the pool path is unavailable.
    lakebase_healthy = False
    try:
        from api.state import get_pool
        pool = await get_pool()
        await pool.fetchval("SELECT 1")
        lakebase_healthy = True
    except Exception:
        try:
            lakebase_healthy = await database_health()
        except Exception:
            lakebase_healthy = False

    return {
        "status": "healthy" if lakebase_healthy else "degraded",
        "services": {
            "lakebase": "connected" if lakebase_healthy else "disconnected",
            "sql_warehouse": "configured" if os.getenv("DATABRICKS_WAREHOUSE_ID") else "not_configured",
            "genie": "configured" if os.getenv("GENIE_SPACE_ID") else "not_configured",
        },
        "version": "1.0.0",
    }


# Serve static files from frontend build (production)
frontend_dist = os.path.join(os.path.dirname(__file__), "frontend", "dist")
if os.path.exists(frontend_dist):
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist, "assets")), name="assets")
    
    # Catch-all route for SPA (must be last)
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """Serve the SPA for all non-API routes."""
        # Don't catch API routes
        if full_path.startswith("api/"):
            return {"error": "Not found"}
        
        # Check if requesting a static file that exists in dist root
        if full_path and not full_path.startswith("api/"):
            static_file = os.path.join(frontend_dist, full_path)
            if os.path.isfile(static_file):
                return FileResponse(static_file)
        
        # Fall back to SPA index.html
        index_path = os.path.join(frontend_dist, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
        return {"error": "Frontend not built. Run: cd frontend && npm run build"}


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )

