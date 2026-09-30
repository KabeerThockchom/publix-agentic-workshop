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
