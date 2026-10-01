"""
State Persistence API endpoints.

Persists user submission state to Lakebase (PostgreSQL) via asyncpg:
- Inventory orders: items submitted via "Submit Order"
- prep items: dough-prep items added via "Add to Schedule"

State is scoped per store_id so each store's submissions are independent.

Connection strategy (tried in order):
1. PG* env vars (auto-injected when Lakebase is an App resource)
2. SDK w.database / w.postgres with generate_database_credential
3. SDK with oauth_token().access_token as password fallback
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import asyncpg
import logging
import os
import uuid
import time

logger = logging.getLogger(__name__)

router = APIRouter()

_pool: Optional[asyncpg.Pool] = None
_pool_created_at: float = 0
TOKEN_LIFETIME_SECONDS = 50 * 60


def _generate_password() -> str:
    """
    Generate a PostgreSQL password using Databricks SDK.

    Tries generate_database_credential first (purpose-built for Lakebase),
    then falls back to oauth_token().access_token (works as PG password too).
    """
    from databricks.sdk import WorkspaceClient

    ws = WorkspaceClient()

    instance_name = os.getenv("LAKEBASE_INSTANCE_NAME")
    if instance_name:
        try:
            instance = ws.database.get_database_instance(name=instance_name)
            cred = ws.database.generate_database_credential(
                request_id=str(uuid.uuid4()),
                instance_names=[instance.name],
            )
            logger.info("State API: password from generate_database_credential")
            return cred.token
        except Exception as e:
            logger.warning(f"State API: generate_database_credential failed: {e}")

    try:
        token = ws.config.oauth_token().access_token
        logger.info("State API: password from oauth_token().access_token")
        return token
    except Exception as e:
        logger.warning(f"State API: oauth_token() failed: {e}")

    raise RuntimeError("Cannot generate Lakebase password via any method")


def _get_connection_config() -> dict:
    """
    Build asyncpg connection config.

    Uses platform-injected PGHOST/PGUSER/PGDATABASE (from the postgres app resource)
    for host/user/database, and generates the password via SDK since the platform
    does not inject PGPASSWORD for Lakebase Autoscaling.

    Falls back entirely to SDK if PG* env vars are not available (local dev).
    """
    from databricks.sdk import WorkspaceClient

    host = os.getenv("PGHOST")
    user = os.getenv("PGUSER")
    database = os.getenv("PGDATABASE") or os.getenv("LAKEBASE_DATABASE_NAME", "databricks_postgres")
    port = int(os.getenv("PGPORT", "5432"))
    password = os.getenv("PGPASSWORD")

    if host and user and password:
        logger.info(f"State API: full PG* env config (host={host}, user={user})")
        return {"host": host, "database": database, "user": user, "password": password, "port": port}

    if not host:
        ws = WorkspaceClient()
        instance_name = os.getenv("LAKEBASE_INSTANCE_NAME")
        if not instance_name:
            raise RuntimeError("Neither PGHOST nor LAKEBASE_INSTANCE_NAME is configured")
        instance = ws.database.get_database_instance(name=instance_name)
        host = instance.read_write_dns
        logger.info(f"State API: host from SDK instance={host}")

    if not user:
        ws = WorkspaceClient()
        try:
            user = ws.current_user.me().user_name
        except Exception:
            user = os.getenv("DATABRICKS_CLIENT_ID")
        logger.info(f"State API: user resolved={user}")

    if not user:
        raise RuntimeError("Cannot resolve PostgreSQL username")

    password = _generate_password()
    logger.info(f"State API: connecting as {user}@{host}/{database}")

    return {"host": host, "database": database, "user": user, "password": password, "port": port}


async def _ensure_tables(pool: asyncpg.Pool):
    """Create tables if they don't exist."""
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS inventory_orders (
                id SERIAL PRIMARY KEY,
                store_id INTEGER NOT NULL,
                ingredient_id INTEGER NOT NULL,
                ingredient_name TEXT NOT NULL,
                suggested_quantity NUMERIC,
                estimated_cost NUMERIC,
                urgency TEXT,
                ordered_at TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE (store_id, ingredient_id)
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS prep_items (
                id SERIAL PRIMARY KEY,
                store_id INTEGER NOT NULL,
                crust_type TEXT NOT NULL,
                recommended_quantity INTEGER,
                suggested_prep_time TEXT,
                confidence NUMERIC,
                added_at TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE (store_id, crust_type)
            )
        """)
        logger.info("State API: tables ensured")


async def get_pool() -> asyncpg.Pool:
    """
    Get or create an asyncpg connection pool.

    Tries platform-injected PG* env vars first (most reliable for Apps),
    then falls back to SDK-based credential generation.
    Recreates the pool before OAuth token expiry (~50 minutes).
    """
    global _pool, _pool_created_at

    now = time.time()
    pool_expired = (now - _pool_created_at) > TOKEN_LIFETIME_SECONDS

    if _pool is not None and not _pool._closed and not pool_expired:
        return _pool

    if _pool is not None and not _pool._closed:
        logger.info("State API: closing stale pool for token refresh")
        await _pool.close()
        _pool = None

    try:
        config = _get_connection_config()
    except Exception as e:
        logger.error(f"State API: connection config failed: {e}", exc_info=True)
        raise HTTPException(status_code=503, detail=f"Lakebase unavailable: {e}")

    try:
        _pool = await asyncpg.create_pool(
            host=config["host"],
            port=config["port"],
            database=config["database"],
            user=config["user"],
            password=config["password"],
            ssl="require",
            min_size=1,
            max_size=5,
            command_timeout=30,
        )
        _pool_created_at = time.time()
        logger.info(f"State API: pool created for {config['database']}")

        await _ensure_tables(_pool)
        return _pool

    except Exception as e:
        logger.error(f"State API: pool creation failed: {e}", exc_info=True)
        _pool = None
        raise HTTPException(status_code=503, detail=f"Lakebase connection failed: {e}")


# === Diagnostic Endpoint ===

@router.get("/debug")
async def state_debug():
    """
    Diagnostic endpoint showing Lakebase connection environment and status.
    Helps troubleshoot connection issues in deployed Apps.
    """
    env_info = {
        "PGHOST": os.getenv("PGHOST"),
        "PGDATABASE": os.getenv("PGDATABASE"),
        "PGUSER": os.getenv("PGUSER"),
        "PGPASSWORD_set": bool(os.getenv("PGPASSWORD")),
        "PGPORT": os.getenv("PGPORT"),
        "LAKEBASE_INSTANCE_NAME": os.getenv("LAKEBASE_INSTANCE_NAME"),
        "LAKEBASE_DATABASE_NAME": os.getenv("LAKEBASE_DATABASE_NAME"),
        "DATABRICKS_CLIENT_ID": os.getenv("DATABRICKS_CLIENT_ID"),
        "DATABRICKS_CLIENT_SECRET_set": bool(os.getenv("DATABRICKS_CLIENT_SECRET")),
        "DATABRICKS_HOST": os.getenv("DATABRICKS_HOST"),
    }

    sdk_info = {}
    try:
        from databricks.sdk import WorkspaceClient
        ws = WorkspaceClient()
        try:
            me = ws.current_user.me()
            sdk_info["current_user"] = me.user_name
            sdk_info["current_user_id"] = str(me.id) if me.id else None
        except Exception as e:
            sdk_info["current_user_error"] = str(e)[:200]

        sdk_info["config_client_id"] = ws.config.client_id
        sdk_info["config_host"] = ws.config.host

        instance_name = os.getenv("LAKEBASE_INSTANCE_NAME")
        if instance_name:
            try:
                inst = ws.database.get_database_instance(name=instance_name)
                sdk_info["instance_dns"] = inst.read_write_dns
                sdk_info["instance_name"] = inst.name
            except Exception as e:
                sdk_info["instance_error"] = str(e)[:200]

        try:
            token = ws.config.oauth_token().access_token
            sdk_info["oauth_token_available"] = True
            sdk_info["oauth_token_length"] = len(token)
        except Exception as e:
            sdk_info["oauth_token_error"] = str(e)[:200]

    except Exception as e:
        sdk_info["sdk_init_error"] = str(e)[:200]

    pool_info = {
        "pool_exists": _pool is not None,
        "pool_closed": _pool._closed if _pool else None,
        "pool_age_seconds": int(time.time() - _pool_created_at) if _pool_created_at else None,
    }

    # Quick connection test
    connection_test = {}
    try:
        pool = await get_pool()
        result = await pool.fetchval("SELECT 1")
        connection_test["status"] = "connected"
        connection_test["select_1"] = result

        tables = await pool.fetch("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public'
        """)
        connection_test["tables"] = [r["table_name"] for r in tables]

    except Exception as e:
        connection_test["status"] = "failed"
        connection_test["error"] = str(e)[:400]

    return {
        "env": env_info,
        "sdk": sdk_info,
        "pool": pool_info,
        "connection_test": connection_test,
    }


# === Pydantic Models ===

class InventoryOrderIn(BaseModel):
    ingredient_id: int
    ingredient_name: str
    suggested_quantity: Optional[float] = None
    estimated_cost: Optional[float] = None
    urgency: Optional[str] = None


class InventoryOrderOut(BaseModel):
    id: int
    store_id: int
    ingredient_id: int
    ingredient_name: str
    suggested_quantity: Optional[float]
    estimated_cost: Optional[float]
    urgency: Optional[str]
    ordered_at: str


class PrepItemIn(BaseModel):
    crust_type: str
    recommended_quantity: Optional[int] = None
    suggested_prep_time: Optional[str] = None
    confidence: Optional[float] = None


class PrepItemOut(BaseModel):
    id: int
    store_id: int
    crust_type: str
    recommended_quantity: Optional[int]
    suggested_prep_time: Optional[str]
    confidence: Optional[float]
    added_at: str


# === Inventory Orders ===

@router.get("/inventory-orders/{store_id}")
async def get_inventory_orders(store_id: int) -> List[InventoryOrderOut]:
    """Get all persisted inventory orders for a store."""
    pool = await get_pool()
    rows = await pool.fetch(
        "SELECT * FROM inventory_orders WHERE store_id = $1 ORDER BY ordered_at DESC",
        store_id,
    )
    return [
        InventoryOrderOut(
            id=r["id"],
            store_id=r["store_id"],
            ingredient_id=r["ingredient_id"],
            ingredient_name=r["ingredient_name"],
            suggested_quantity=float(r["suggested_quantity"]) if r["suggested_quantity"] else None,
            estimated_cost=float(r["estimated_cost"]) if r["estimated_cost"] else None,
            urgency=r["urgency"],
            ordered_at=r["ordered_at"].strftime("%b %d, %I:%M %p") if r["ordered_at"] else "",
        )
        for r in rows
    ]


@router.post("/inventory-orders/{store_id}")
async def submit_inventory_orders(store_id: int, items: List[InventoryOrderIn]) -> dict:
    """Persist inventory order submissions. Uses upsert to avoid duplicates."""
    pool = await get_pool()
    inserted = 0
    async with pool.acquire() as conn:
        for item in items:
            await conn.execute(
                """
                INSERT INTO inventory_orders (store_id, ingredient_id, ingredient_name, suggested_quantity, estimated_cost, urgency)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (store_id, ingredient_id) DO UPDATE SET
                    ingredient_name = EXCLUDED.ingredient_name,
                    suggested_quantity = EXCLUDED.suggested_quantity,
                    estimated_cost = EXCLUDED.estimated_cost,
                    urgency = EXCLUDED.urgency,
                    ordered_at = NOW()
                """,
                store_id,
                item.ingredient_id,
                item.ingredient_name,
                item.suggested_quantity,
                item.estimated_cost,
                item.urgency,
            )
            inserted += 1
    return {"status": "ok", "inserted": inserted}


@router.delete("/inventory-orders/{store_id}")
async def clear_inventory_orders(store_id: int) -> dict:
    """Clear all inventory orders for a store."""
    pool = await get_pool()
    result = await pool.execute(
        "DELETE FROM inventory_orders WHERE store_id = $1",
        store_id,
    )
    count = int(result.split()[-1]) if result else 0
    return {"status": "ok", "deleted": count}


# === prep items ===

@router.get("/prep-items/{store_id}")
async def get_prep_items(store_id: int) -> List[PrepItemOut]:
    """Get all persisted prep items for a store."""
    pool = await get_pool()
    rows = await pool.fetch(
        "SELECT * FROM prep_items WHERE store_id = $1 ORDER BY added_at DESC",
        store_id,
    )
    return [
        PrepItemOut(
            id=r["id"],
            store_id=r["store_id"],
            crust_type=r["crust_type"],
            recommended_quantity=r["recommended_quantity"],
            suggested_prep_time=r["suggested_prep_time"],
            confidence=float(r["confidence"]) if r["confidence"] else None,
            added_at=r["added_at"].strftime("%b %d, %I:%M %p") if r["added_at"] else "",
        )
        for r in rows
    ]


@router.post("/prep-items/{store_id}")
async def submit_prep_items(store_id: int, items: List[PrepItemIn]) -> dict:
    """Persist prep additions. Uses upsert to avoid duplicates."""
    pool = await get_pool()
    inserted = 0
    async with pool.acquire() as conn:
        for item in items:
            await conn.execute(
                """
                INSERT INTO prep_items (store_id, crust_type, recommended_quantity, suggested_prep_time, confidence)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (store_id, crust_type) DO UPDATE SET
                    recommended_quantity = EXCLUDED.recommended_quantity,
                    suggested_prep_time = EXCLUDED.suggested_prep_time,
                    confidence = EXCLUDED.confidence,
                    added_at = NOW()
                """,
                store_id,
                item.crust_type,
                item.recommended_quantity,
                item.suggested_prep_time,
                item.confidence,
            )
            inserted += 1
    return {"status": "ok", "inserted": inserted}


@router.delete("/prep-items/{store_id}")
async def clear_prep_items(store_id: int) -> dict:
    """Clear all prep items for a store."""
    pool = await get_pool()
    result = await pool.execute(
        "DELETE FROM prep_items WHERE store_id = $1",
        store_id,
    )
    count = int(result.split()[-1]) if result else 0
    return {"status": "ok", "deleted": count}
