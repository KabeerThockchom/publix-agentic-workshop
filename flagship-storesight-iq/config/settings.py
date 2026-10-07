"""
Application settings using Pydantic BaseSettings.

Loads configuration from environment variables and .env file.
In Databricks Apps, most values are auto-configured.
For local development, uses ~/.databrickscfg or .env file.
"""

import os
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment."""

    # === Databricks SQL Warehouse ===
    databricks_warehouse_id: Optional[str] = Field(
        default=None,
        description="SQL Warehouse ID for querying Delta tables",
    )

    # === Unity Catalog ===
    catalog_name: str = Field(
        default="publix_technology",
        description="Shared Unity Catalog name (publix_technology)",
    )
    schema_name: str = Field(
        default="storesight_iq_publix",
        description="Schema name within the catalog",
    )

    # === Lakebase Configuration ===
    lakebase_instance_name: Optional[str] = Field(
        default="publix-build-studio-lb",
        description="Lakebase PostgreSQL instance name",
    )
    lakebase_database_name: Optional[str] = Field(
        default="databricks_postgres",
        description="Database name within Lakebase instance",
    )
    databricks_database_port: int = Field(
        default=5432,
        description="PostgreSQL port",
    )

    # === Database Pool Settings ===
    db_pool_size: int = Field(default=5)
    db_max_overflow: int = Field(default=10)
    db_command_timeout: int = Field(default=30)
    db_pool_timeout: int = Field(default=10)
    db_pool_recycle_interval: int = Field(default=3600)

    # === Model Serving Endpoints ===
    demand_forecast_endpoint: str = Field(
        default="storesight-publix-demand-forecast",
        description="Demand forecasting model endpoint",
    )
    labor_optimizer_endpoint: str = Field(
        default="storesight-publix-labor-optimizer",
        description="Labor optimization model endpoint",
    )
    inventory_predictor_endpoint: str = Field(
        default="storesight-publix-inventory-predictor",
        description="Inventory prediction model endpoint",
    )
    prep_scheduler_endpoint: str = Field(
        default="storesight-publix-prep-scheduler",
        description="Prep/production schedule optimizer endpoint",
    )

    # === Genie Space ===
    genie_space_id: Optional[str] = Field(
        default=None,
        description="Genie Space ID for AI chatbot",
    )

    # === Databricks Workspace (for Genie embed iframe) ===
    # Injected by the Databricks Apps runtime as the DATABRICKS_HOST env var; no
    # hardcoded workspace URL. Used only to build the Genie embed iframe URL.
    databricks_host: Optional[str] = Field(
        default=None,
        description="Databricks workspace host, from the DATABRICKS_HOST env var",
    )
    # Plain `str` (NOT Optional[str]): pydantic-settings JSON-decodes env values
    # for union/complex-typed fields, so an all-numeric WORKSPACE_ID (every
    # AWS/GCP org id) would parse to an int and fail str validation. A plain str
    # is used verbatim from the env. Empty string = unset (Genie embed hidden).
    workspace_id: str = Field(
        default="7405614888461357",
        description="Workspace/org id used in the Genie embed URL (?o=...)",
    )

    # === External APIs ===
    ticketmaster_api_key: Optional[str] = Field(
        default=None,
        description="Ticketmaster Discovery API key",
    )

    # === Pagination Defaults ===
    default_limit: int = Field(default=100)
    max_limit: int = Field(default=1000)

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "allow",
    }

    @property
    def table_prefix(self) -> str:
        """Get the full table prefix (catalog.schema)."""
        return f"{self.catalog_name}.{self.schema_name}"

    def get_table_path(self, table_name: str) -> str:
        """Get full path for a table."""
        return f"{self.table_prefix}.{table_name}"


# Singleton instance
settings = Settings()


def get_settings() -> Settings:
    """
    Dependency injection function for FastAPI endpoints.
    
    Returns:
        The application settings instance.
    """
    return settings





