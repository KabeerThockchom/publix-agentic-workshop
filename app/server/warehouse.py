"""Read-side data access via Databricks SQL warehouse (statement execution)."""
from decimal import Decimal
from typing import Any

from databricks.sdk.service.sql import StatementState

from .config import GOLD_TABLE, PERF_VIEW, PRICE_TABLE, WAREHOUSE_ID, get_workspace_client


def _coerce(v: Any) -> Any:
    if v is None:
        return None
    return v


def run_query(sql: str) -> list[dict[str, Any]]:
    """Execute a read query on the warehouse and return a list of dict rows."""
    w = get_workspace_client()
    resp = w.statement_execution.execute_statement(
        warehouse_id=WAREHOUSE_ID,
        statement=sql,
        wait_timeout="30s",
    )
    if resp.status and resp.status.state != StatementState.SUCCEEDED:
        msg = resp.status.error.message if resp.status.error else "unknown error"
        raise RuntimeError(f"Query failed: {msg}")

    cols = [c.name for c in resp.manifest.schema.columns] if resp.manifest else []
    data = resp.result.data_array if resp.result and resp.result.data_array else []
    return [dict(zip(cols, [_coerce(v) for v in row])) for row in data]


def _to_num(v: Any) -> float:
    if v is None:
        return 0.0
    if isinstance(v, Decimal):
        return float(v)
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def summary() -> dict[str, Any]:
    rows = run_query(
        f"""
        SELECT
          CAST(SUM(revenue) AS DOUBLE) AS total_revenue,
          CAST(SUM(units_sold) AS BIGINT) AS total_units,
          COUNT(DISTINCT store_number) AS stores,
          COUNT(DISTINCT item_id) AS items,
          CAST(MIN(sales_date) AS STRING) AS start_date,
          CAST(MAX(sales_date) AS STRING) AS end_date
        FROM {GOLD_TABLE}
        """
    )
    r = rows[0] if rows else {}
    return {
        "total_revenue": _to_num(r.get("total_revenue")),
        "total_units": int(_to_num(r.get("total_units"))),
        "stores": int(_to_num(r.get("stores"))),
        "items": int(_to_num(r.get("items"))),
        "start_date": r.get("start_date"),
        "end_date": r.get("end_date"),
    }


def by_store() -> list[dict[str, Any]]:
    rows = run_query(
        f"""
        SELECT
          store_number,
          CAST(SUM(revenue) AS DOUBLE) AS revenue,
          CAST(SUM(units_sold) AS BIGINT) AS units,
          COUNT(DISTINCT item_id) AS items
        FROM {PERF_VIEW}
        GROUP BY store_number
        ORDER BY revenue DESC
        """
    )
    return [
        {
            "store_number": str(r.get("store_number")),
            "revenue": _to_num(r.get("revenue")),
            "units": int(_to_num(r.get("units"))),
            "items": int(_to_num(r.get("items"))),
        }
        for r in rows
    ]


def by_item() -> list[dict[str, Any]]:
    rows = run_query(
        f"""
        SELECT
          item_id,
          item_name,
          item_category,
          CAST(SUM(revenue) AS DOUBLE) AS revenue,
          CAST(SUM(units_sold) AS BIGINT) AS units
        FROM {GOLD_TABLE}
        GROUP BY item_id, item_name, item_category
        ORDER BY revenue DESC
        """
    )
    return [
        {
            "item_id": str(r.get("item_id")),
            "item_name": r.get("item_name"),
            "item_category": r.get("item_category"),
            "revenue": _to_num(r.get("revenue")),
            "units": int(_to_num(r.get("units"))),
        }
        for r in rows
    ]


def trend() -> list[dict[str, Any]]:
    rows = run_query(
        f"""
        SELECT
          CAST(sales_date AS STRING) AS sales_date,
          CAST(SUM(revenue) AS DOUBLE) AS revenue,
          CAST(SUM(units_sold) AS BIGINT) AS units
        FROM {GOLD_TABLE}
        GROUP BY sales_date
        ORDER BY sales_date
        """
    )
    return [
        {
            "sales_date": r.get("sales_date"),
            "revenue": _to_num(r.get("revenue")),
            "units": int(_to_num(r.get("units"))),
        }
        for r in rows
    ]


def price_updates(limit: int = 50) -> list[dict[str, Any]]:
    rows = run_query(
        f"""
        SELECT
          event_timestamp,
          item_id,
          item_name,
          old_price,
          new_price,
          effective_date
        FROM {PRICE_TABLE}
        ORDER BY event_timestamp DESC
        LIMIT {int(limit)}
        """
    )
    out = []
    for r in rows:
        old_p = _to_num(r.get("old_price"))
        new_p = _to_num(r.get("new_price"))
        pct = ((new_p - old_p) / old_p * 100.0) if old_p else 0.0
        out.append(
            {
                "event_timestamp": r.get("event_timestamp"),
                "item_id": str(r.get("item_id")),
                "item_name": r.get("item_name"),
                "old_price": old_p,
                "new_price": new_p,
                "pct_change": round(pct, 2),
                "effective_date": r.get("effective_date"),
            }
        )
    return out


def items_catalog() -> list[dict[str, Any]]:
    """Distinct items for form dropdowns."""
    rows = run_query(
        f"SELECT DISTINCT item_id, item_name FROM {GOLD_TABLE} ORDER BY item_id"
    )
    return [{"item_id": str(r.get("item_id")), "item_name": r.get("item_name")} for r in rows]


def stores_catalog() -> list[str]:
    rows = run_query(
        f"SELECT DISTINCT store_number FROM {GOLD_TABLE} ORDER BY store_number"
    )
    return [str(r.get("store_number")) for r in rows]
