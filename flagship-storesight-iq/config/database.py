"""
Database configuration for Lakebase (PostgreSQL) and SQL Warehouse connections.

This module handles:
1. Lakebase async PostgreSQL connections with automatic OAuth token refresh
2. SQL Warehouse connections for querying Delta tables
3. Connection pooling and health monitoring

Based on Databricks Apps best practices:
https://docs.databricks.com/aws/en/dev-tools/databricks-apps/
"""

import asyncio
import logging
import os
import time
import uuid
from typing import AsyncGenerator, Optional, Dict, List, Union

import pandas as pd
from databricks.sdk import WorkspaceClient
from databricks.sdk.core import Config
from databricks import sql
from dotenv import load_dotenv
from sqlalchemy import URL, event, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

load_dotenv()
logger = logging.getLogger(__name__)

# === Global Variables ===
engine: Optional[AsyncEngine] = None
AsyncSessionLocal: Optional[sessionmaker] = None
workspace_client: Optional[WorkspaceClient] = None
database_instance = None

# Token management for background refresh
postgres_password: Optional[str] = None
last_password_refresh: float = 0
token_refresh_task: Optional[asyncio.Task] = None
# True when connecting via injected PG* env vars (project-based Lakebase);
# in this mode the password comes from the resource, not OAuth token refresh.
_using_pg_env: bool = False

# Databricks SDK config for SQL connections
_databricks_cfg: Optional[Config] = None


def get_databricks_config() -> Config:
    """Get or create Databricks SDK configuration."""
    global _databricks_cfg
    if _databricks_cfg is None:
        _databricks_cfg = Config()
    return _databricks_cfg


def get_workspace_client() -> WorkspaceClient:
    """Get or create Databricks Workspace client."""
    global workspace_client
    if workspace_client is None:
        workspace_client = WorkspaceClient()
    return workspace_client


# ============================================
# SQL Warehouse Connection (for Delta Tables)
# ============================================

_sql_connections: Dict[str, any] = {}


def get_sql_connection(warehouse_id: str):
    """
    Get a connection to Databricks SQL Warehouse.
    
    Args:
        warehouse_id: The SQL Warehouse ID
        
    Returns:
        SQL connection object
    """
    if warehouse_id not in _sql_connections:
        cfg = get_databricks_config()
        
        # Strip protocol from hostname (cfg.host may include https://)
        server_hostname = cfg.host
        if server_hostname:
            server_hostname = server_hostname.replace("https://", "").replace("http://", "").rstrip("/")
        
        http_path = f"/sql/1.0/warehouses/{warehouse_id}"
        
        logger.info(f"Creating SQL connection to {server_hostname} with warehouse {warehouse_id}")
        
        _sql_connections[warehouse_id] = sql.connect(
            server_hostname=server_hostname,
            http_path=http_path,
            credentials_provider=lambda: cfg.authenticate,
            # Performance optimizations
            _disable_cloud_fetch_for_testing=False,  # Use cloud fetch when pyarrow is available
        )
    return _sql_connections[warehouse_id]


def close_sql_connections():
    """Close all SQL Warehouse connections."""
    global _sql_connections
    for conn in _sql_connections.values():
        try:
            conn.close()
        except Exception as e:
            logger.warning(f"Error closing SQL connection: {e}")
    _sql_connections.clear()


def query_sql(
    sql_query: str,
    warehouse_id: str,
    as_dict: bool = True
) -> Union[List[Dict], pd.DataFrame]:
    """
    Execute a query against Databricks SQL Warehouse.
    
    Args:
        sql_query: SQL query to execute
        warehouse_id: The SQL Warehouse ID
        as_dict: Return as list of dicts (True) or DataFrame (False)
        
    Returns:
        Query results
    """
    conn = get_sql_connection(warehouse_id)
    
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql_query)
            result = cursor.fetchall()
            columns = [col[0] for col in cursor.description]
            
            if as_dict:
                return [dict(zip(columns, row)) for row in result]
            else:
                return pd.DataFrame(result, columns=columns)
    except Exception as e:
        logger.error(f"SQL query failed: {e}")
        raise Exception(f"Query failed: {str(e)}")


# ============================================
# Lakebase PostgreSQL Connection (for OLTP)
# ============================================

async def refresh_token_background():
    """Background task to refresh Lakebase OAuth tokens every 50 minutes."""
    global postgres_password, last_password_refresh, workspace_client, database_instance

    # In PG-env mode the password is supplied by the attached postgres resource,
    # not an OAuth token we mint — nothing to refresh.
    if _using_pg_env:
        logger.info("Background token refresh: skipped (PG env mode)")
        return

    while True:
        try:
            await asyncio.sleep(50 * 60)  # Wait 50 minutes (tokens expire after 1 hour)
            logger.info("Background token refresh: Generating fresh PostgreSQL OAuth token")

            cred = workspace_client.database.generate_database_credential(
                request_id=str(uuid.uuid4()),
                instance_names=[database_instance.name],
            )
            postgres_password = cred.token
            last_password_refresh = time.time()
            logger.info("Background token refresh: Token updated successfully")

        except Exception as e:
            logger.error(f"Background token refresh failed: {e}")


def init_engine():
    """
    Initialize Lakebase PostgreSQL connection with automatic token refresh.
    
    Uses SQLAlchemy async engine with connection pooling.
    OAuth tokens are refreshed automatically via background task.
    """
    global engine, AsyncSessionLocal, workspace_client, database_instance
    global postgres_password, last_password_refresh, _using_pg_env

    try:
        # === Path 1: PG* env vars injected by an attached "postgres" app resource ===
        # Project-based Lakebase (Database projects) surfaces standard libpq env vars
        # (PGHOST/PGUSER/PGPASSWORD/PGDATABASE/PGPORT) rather than the legacy
        # instance API. Prefer these when present — no OAuth token refresh needed.
        pg_host = os.getenv("PGHOST")
        pg_password = os.getenv("PGPASSWORD")
        if pg_host and pg_password:
            _using_pg_env = True
            postgres_password = pg_password
            last_password_refresh = time.time()

            database_name = os.getenv("PGDATABASE") or os.getenv("LAKEBASE_DATABASE_NAME") or "databricks_postgres"
            username = os.getenv("PGUSER") or os.getenv("DATABRICKS_CLIENT_ID")

            url = URL.create(
                drivername="postgresql+asyncpg",
                username=username,
                password="",  # set by do_connect event handler below
                host=pg_host,
                port=int(os.getenv("PGPORT", "5432")),
                database=database_name,
            )
            logger.info(f"Lakebase: using injected PG* env vars (host={pg_host}, db={database_name})")

            engine = create_async_engine(
                url,
                pool_pre_ping=True,
                echo=False,
                pool_size=int(os.getenv("DB_POOL_SIZE", "5")),
                max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "10")),
                pool_timeout=int(os.getenv("DB_POOL_TIMEOUT", "10")),
                pool_recycle=int(os.getenv("DB_POOL_RECYCLE_INTERVAL", "3600")),
                connect_args={
                    "command_timeout": int(os.getenv("DB_COMMAND_TIMEOUT", "30")),
                    "server_settings": {"application_name": "storesight_iq_app"},
                    "ssl": os.getenv("PGSSLMODE", "require"),
                },
            )

            @event.listens_for(engine.sync_engine, "do_connect")
            def provide_token_pgenv(dialect, conn_rec, cargs, cparams):
                cparams["password"] = postgres_password

            AsyncSessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
            logger.info(f"Lakebase engine initialized for {database_name} (PG env mode)")
            return

        # === Path 2: legacy instance-based Lakebase (OAuth token refresh) ===
        workspace_client = get_workspace_client()

        instance_name = os.getenv("LAKEBASE_INSTANCE_NAME")
        if not instance_name:
            raise RuntimeError("LAKEBASE_INSTANCE_NAME environment variable is required")

        # Get database instance details
        database_instance = workspace_client.database.get_database_instance(
            name=instance_name
        )

        # Generate initial OAuth credentials
        cred = workspace_client.database.generate_database_credential(
            request_id=str(uuid.uuid4()),
            instance_names=[database_instance.name]
        )
        postgres_password = cred.token
        last_password_refresh = time.time()
        logger.info("Lakebase: Initial credentials generated")

        # Build connection URL
        database_name = os.getenv("LAKEBASE_DATABASE_NAME", database_instance.name)
        username = (
            os.getenv("DATABRICKS_CLIENT_ID")
            or workspace_client.current_user.me().user_name
            or None
        )

        url = URL.create(
            drivername="postgresql+asyncpg",
            username=username,
            password="",  # Set by event handler
            host=database_instance.read_write_dns,
            port=int(os.getenv("DATABRICKS_DATABASE_PORT", "5432")),
            database=database_name,
        )

        # Create async engine with connection pooling
        engine = create_async_engine(
            url,
            pool_pre_ping=False,
            echo=False,
            pool_size=int(os.getenv("DB_POOL_SIZE", "5")),
            max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "10")),
            pool_timeout=int(os.getenv("DB_POOL_TIMEOUT", "10")),
            pool_recycle=int(os.getenv("DB_POOL_RECYCLE_INTERVAL", "3600")),
            connect_args={
                "command_timeout": int(os.getenv("DB_COMMAND_TIMEOUT", "30")),
                "server_settings": {
                    "application_name": "storesight_iq_app",
                },
                "ssl": "require",
            },
        )

        # Register token provider for new connections
        @event.listens_for(engine.sync_engine, "do_connect")
        def provide_token(dialect, conn_rec, cargs, cparams):
            global postgres_password
            cparams["password"] = postgres_password

        # Create session factory
        AsyncSessionLocal = sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False
        )

        logger.info(f"Lakebase engine initialized for {database_name}")

    except Exception as e:
        logger.error(f"Error initializing Lakebase: {e}")
        raise RuntimeError(f"Failed to initialize Lakebase: {e}") from e


async def start_token_refresh():
    """Start the background token refresh task."""
    global token_refresh_task
    if token_refresh_task is None or token_refresh_task.done():
        token_refresh_task = asyncio.create_task(refresh_token_background())
        logger.info("Background token refresh task started")


async def stop_token_refresh():
    """Stop the background token refresh task."""
    global token_refresh_task
    if token_refresh_task and not token_refresh_task.done():
        token_refresh_task.cancel()
        try:
            await token_refresh_task
        except asyncio.CancelledError:
            pass
        logger.info("Background token refresh task stopped")


async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Get an async database session for Lakebase.
    
    Usage:
        async def my_endpoint(db: AsyncSession = Depends(get_async_db)):
            result = await db.execute(select(MyModel))
    """
    if AsyncSessionLocal is None:
        raise RuntimeError("Lakebase engine not initialized; call init_engine() first")
    async with AsyncSessionLocal() as session:
        yield session


def check_database_exists() -> bool:
    """Check if the Lakebase database is available."""
    # PG* env vars injected by an attached postgres resource (project-based
    # Lakebase) mean the database is reachable without the instance API.
    if os.getenv("PGHOST") and os.getenv("PGPASSWORD"):
        logger.info("Lakebase available via injected PG* env vars")
        return True
    try:
        client = get_workspace_client()
        instance_name = os.getenv("LAKEBASE_INSTANCE_NAME")

        if not instance_name:
            logger.warning("LAKEBASE_INSTANCE_NAME not set - Lakebase disabled")
            return False

        client.database.get_database_instance(name=instance_name)
        logger.info(f"Lakebase instance '{instance_name}' found")
        return True

    except Exception as e:
        if "not found" in str(e).lower() or "resource not found" in str(e).lower():
            logger.info(f"Lakebase instance not found - run setup notebook first")
        else:
            logger.error(f"Error checking Lakebase instance: {e}")
        return False


async def database_health() -> bool:
    """Check Lakebase database connection health."""
    global engine

    if engine is None:
        logger.warning("Lakebase engine not initialized")
        return False

    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
            logger.debug("Lakebase connection healthy")
            return True
    except Exception as e:
        logger.error(f"Lakebase health check failed: {e}")
        return False


def close_connections():
    """Close all database connections (called on shutdown)."""
    close_sql_connections()
    logger.info("All database connections closed")


