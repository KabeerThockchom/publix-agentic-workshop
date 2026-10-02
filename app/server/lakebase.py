"""Read/write OLTP access to Lakebase Postgres (public.store_actions).

In a deployed Databricks App the platform injects PGHOST/PGPORT/PGDATABASE/PGUSER
(and PGSSLMODE) when a `database` resource is attached. The Postgres password is a
short-lived OAuth credential minted from the Lakebase endpoint. Locally the same
path works via the CLI profile.

Degrades gracefully: if Lakebase is not configured/reachable, the API surfaces a
clear `configured: false` signal instead of crashing.
"""
import os
import threading
import time
from typing import Any, Optional

import psycopg2
import psycopg2.extras

from .config import LAKEBASE_ENDPOINT, get_workspace_client

_TOKEN_TTL = 40 * 60  # refresh well before the 1h OAuth expiry
_lock = threading.Lock()
_token_cache: dict[str, Any] = {"token": None, "ts": 0.0}


def is_configured() -> bool:
    return bool(os.environ.get("PGHOST"))


# Schema holding the synced/snapshotted dashboard tables (gold + prices).
READ_SCHEMA = os.environ.get("LAKEBASE_READ_SCHEMA", "public")
_GOLD = f"{READ_SCHEMA}.gold_store_item_daily"
_PRICES = f"{READ_SCHEMA}.silver_tpr_prices"

_reads_ok: Optional[bool] = None


def reads_enabled() -> bool:
    """True when the Lakebase dashboard tables exist and are readable.

    Cached after the first probe so /config and every read path share one answer.
    """
    global _reads_ok
    if not is_configured():
        return False
    if _reads_ok is not None:
        return _reads_ok
    try:
        def _probe(conn):
            with conn.cursor() as cur:
                cur.execute(f"SELECT 1 FROM {_GOLD} LIMIT 1")
                cur.fetchone()
                cur.execute(f"SELECT 1 FROM {_PRICES} LIMIT 1")
                cur.fetchone()
            return True

        _reads_ok = _run(_probe)
    except Exception:
        _reads_ok = False
    return _reads_ok


def _mint_token() -> str:
    """Mint a Postgres OAuth credential for the Lakebase endpoint."""
    w = get_workspace_client()
    cred = w.postgres.generate_database_credential(endpoint=LAKEBASE_ENDPOINT)
    return cred.token


def _get_token() -> str:
    now = time.time()
    with _lock:
        if _token_cache["token"] and (now - _token_cache["ts"]) < _TOKEN_TTL:
            return _token_cache["token"]
        # Prefer a platform-injected password if present, else mint one.
        token = os.environ.get("PGPASSWORD") or _mint_token()
        _token_cache["token"] = token
        _token_cache["ts"] = now
        return token


def _connect():
    return psycopg2.connect(
        host=os.environ["PGHOST"],
        port=int(os.environ.get("PGPORT", "5432")),
        dbname=os.environ.get("PGDATABASE", "publix_app"),
        user=os.environ["PGUSER"],
        password=_get_token(),
        sslmode=os.environ.get("PGSSLMODE", "require"),
        connect_timeout=15,
    )


def _run(fn):
    """Run fn(conn) with one retry on a fresh token (handles stale creds/scale-to-zero)."""
    try:
        conn = _connect()
    except Exception:
        with _lock:
            _token_cache["token"] = None
        conn = _connect()
    try:
        return fn(conn)
    finally:
        conn.close()


ALLOWED_ACTIONS = {"refund", "price_override", "whatif"}


def insert_action(
    store_number: str,
    item_id: str,
    action_type: str,
    amount: Optional[float],
    note: Optional[str],
    created_by: str,
) -> dict[str, Any]:
    if action_type not in ALLOWED_ACTIONS:
        raise ValueError(f"action_type must be one of {sorted(ALLOWED_ACTIONS)}")

    def _do(conn):
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO public.store_actions
                    (store_number, item_id, action_type, amount, note, created_by)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING action_id, store_number, item_id, action_type,
                          amount, note, created_by, created_at
                """,
                (store_number, item_id, action_type, amount, note, created_by),
            )
            row = cur.fetchone()
            conn.commit()
            return _serialize(row)

    return _run(_do)


def recent_actions(limit: int = 25) -> list[dict[str, Any]]:
    def _do(conn):
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT action_id, store_number, item_id, action_type,
                       amount, note, created_by, created_at
                FROM public.store_actions
                ORDER BY created_at DESC, action_id DESC
                LIMIT %s
                """,
                (int(limit),),
            )
            return [_serialize(r) for r in cur.fetchall()]

    return _run(_do)


def delete_action(action_id: int) -> bool:
    def _do(conn):
        with conn.cursor() as cur:
            cur.execute("DELETE FROM public.store_actions WHERE action_id = %s", (action_id,))
            conn.commit()
            return cur.rowcount > 0

    return _run(_do)


def _serialize(row: Optional[dict]) -> Optional[dict]:
    if row is None:
        return None
    out = dict(row)
    if out.get("amount") is not None:
        out["amount"] = float(out["amount"])
    if out.get("created_at") is not None:
        out["created_at"] = out["created_at"].isoformat()
    if out.get("action_id") is not None:
        out["action_id"] = int(out["action_id"])
    return out


# --- Snappy dashboard reads served from Lakebase Postgres (LTAP) --------------
# These read from the synced/snapshotted `gold_store_item_daily` and
# `price_updates` tables in Lakebase instead of round-tripping to the SQL
# warehouse. The API layer falls back to the warehouse if these raise.

def _f(v: Any) -> float:
    if v is None:
        return 0.0
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _query(sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    def _do(conn):
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return [dict(r) for r in cur.fetchall()]

    return _run(_do)


def summary() -> dict[str, Any]:
    rows = _query(
        f"""
        SELECT SUM(revenue) AS total_revenue,
               SUM(units_sold) AS total_units,
               COUNT(DISTINCT store_number) AS stores,
               COUNT(DISTINCT item_id) AS items,
               CAST(MIN(sales_date) AS TEXT) AS start_date,
               CAST(MAX(sales_date) AS TEXT) AS end_date
        FROM {_GOLD}
        """
    )
    r = rows[0] if rows else {}
    return {
        "total_revenue": _f(r.get("total_revenue")),
        "total_units": int(_f(r.get("total_units"))),
        "stores": int(_f(r.get("stores"))),
        "items": int(_f(r.get("items"))),
        "start_date": r.get("start_date"),
        "end_date": r.get("end_date"),
    }


def by_store() -> list[dict[str, Any]]:
    rows = _query(
        f"""
        SELECT store_number,
               SUM(revenue) AS revenue,
               SUM(units_sold) AS units,
               COUNT(DISTINCT item_id) AS items
        FROM {_GOLD}
        GROUP BY store_number
        ORDER BY revenue DESC
        """
    )
    return [
        {
            "store_number": str(r.get("store_number")),
            "revenue": _f(r.get("revenue")),
            "units": int(_f(r.get("units"))),
            "items": int(_f(r.get("items"))),
        }
        for r in rows
    ]


def by_item() -> list[dict[str, Any]]:
    rows = _query(
        f"""
        SELECT item_id, item_name, item_category,
               SUM(revenue) AS revenue,
               SUM(units_sold) AS units
        FROM {_GOLD}
        GROUP BY item_id, item_name, item_category
        ORDER BY revenue DESC
        """
    )
    return [
        {
            "item_id": str(r.get("item_id")),
            "item_name": r.get("item_name"),
            "item_category": r.get("item_category"),
            "revenue": _f(r.get("revenue")),
            "units": int(_f(r.get("units"))),
        }
        for r in rows
    ]


def trend() -> list[dict[str, Any]]:
    rows = _query(
        f"""
        SELECT CAST(sales_date AS TEXT) AS sales_date,
               SUM(revenue) AS revenue,
               SUM(units_sold) AS units
        FROM {_GOLD}
        GROUP BY sales_date
        ORDER BY sales_date
        """
    )
    return [
        {
            "sales_date": r.get("sales_date"),
            "revenue": _f(r.get("revenue")),
            "units": int(_f(r.get("units"))),
        }
        for r in rows
    ]


def price_updates(limit: int = 50) -> list[dict[str, Any]]:
    rows = _query(
        f"""
        SELECT event_ts_str AS event_timestamp, item_code, selling_price, deal_price, effective_date_str AS effective_date
        FROM {_PRICES}
        ORDER BY event_ts_str DESC
        LIMIT %s
        """,
        (int(limit),),
    )
    out = []
    for r in rows:
        selling_p = _f(r.get("selling_price"))
        deal_p = _f(r.get("deal_price"))
        pct = ((deal_p - selling_p) / selling_p * 100.0) if selling_p else 0.0
        out.append(
            {
                "event_timestamp": r.get("event_timestamp"),
                "item_id": str(r.get("item_code")),
                "item_name": r.get("item_code"),
                "old_price": selling_p,
                "new_price": deal_p,
                "pct_change": round(pct, 2),
                "effective_date": r.get("effective_date"),
            }
        )
    return out


def items_catalog() -> list[dict[str, Any]]:
    rows = _query(
        f"SELECT DISTINCT item_id, item_name FROM {_GOLD} ORDER BY item_id"
    )
    return [{"item_id": str(r.get("item_id")), "item_name": r.get("item_name")} for r in rows]


def stores_catalog() -> list[str]:
    rows = _query(f"SELECT DISTINCT store_number FROM {_GOLD} ORDER BY store_number")
    return [str(r.get("store_number")) for r in rows]
