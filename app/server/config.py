"""Dual-mode config: runs in Databricks Apps (ambient SP auth) or locally (CLI profile).

Adapted from the proven build-studio pattern. In-app we use the ambient service
principal; locally we fall back to a CLI profile (DATABRICKS_CONFIG_PROFILE /
DATABRICKS_PROFILE, defaulting to `publix-workshop`).
"""
import os
from functools import lru_cache

from databricks.sdk import WorkspaceClient

IS_DATABRICKS_APP = bool(os.environ.get("DATABRICKS_APP_NAME"))

# --- Resource / model config (override via env in app.yaml) ---
WAREHOUSE_ID = os.environ.get("DATABRICKS_WAREHOUSE_ID", "<warehouse-id>")
# Each workshop participant should set PUBLIX_CATALOG to their own publix_agentic_<yourname>
# Default below is the reference app's catalog; participants override it in app.yaml or environment
CATALOG = os.environ.get("PUBLIX_CATALOG", "publix_agentic_workshop")
GOLD_TABLE = f"{CATALOG}.medallion.gold_store_item_daily"
PERF_VIEW = f"{CATALOG}.medallion.store_performance_metrics"
PRICE_TABLE = f"{CATALOG}.bronze.price_updates"

# Lakebase endpoint resource path (used to mint a Postgres OAuth credential).
LAKEBASE_ENDPOINT = (
    os.environ.get("ENDPOINT_NAME")
    or os.environ.get("LAKEBASE_ENDPOINT")
    or "projects/<lakebase-instance>/branches/production/endpoints/primary"
)

# Genie space id is supplied separately; left as a placeholder until configured.
GENIE_SPACE_ID = (os.environ.get("GENIE_SPACE_ID") or "").strip()

# Sonnet 5 rejects the `temperature` param - callers must omit it.
SERVING_ENDPOINT = os.environ.get("SERVING_ENDPOINT", "databricks-claude-sonnet-5")


@lru_cache(maxsize=1)
def get_workspace_client() -> WorkspaceClient:
    if IS_DATABRICKS_APP:
        return WorkspaceClient()
    profile = os.environ.get("DATABRICKS_CONFIG_PROFILE") or os.environ.get(
        "DATABRICKS_PROFILE", "publix-workshop"
    )
    return WorkspaceClient(profile=profile)


def get_oauth_token() -> str:
    """Bearer token that works for OAuth (U2M/M2M) and PAT profiles alike."""
    client = get_workspace_client()
    tok = client.config.token
    if tok:
        return tok
    auth = client.config.authenticate()
    return auth.get("Authorization", "").removeprefix("Bearer ").strip()


def get_workspace_host() -> str:
    if IS_DATABRICKS_APP:
        host = os.environ.get("DATABRICKS_HOST", "")
        if host and not host.startswith("http"):
            host = f"https://{host}"
        return host
    return get_workspace_client().config.host
