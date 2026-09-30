"""API routes for Store Pulse."""
import logging
import re
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import genie, lakebase, warehouse
from ..config import GENIE_SPACE_ID, get_workspace_host

log = logging.getLogger("store_pulse")
router = APIRouter(prefix="/api")


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/config")
def config():
    embed_url = None
    if GENIE_SPACE_ID:
        try:
            host = get_workspace_host().rstrip("/")
            embed_url = f"{host}/embed/genie/rooms/{GENIE_SPACE_ID}"
            m = re.search(r"adb-(\d+)\.", host)
            if m:
                embed_url += f"?o={m.group(1)}"
        except Exception:
            embed_url = None
    return {
        "app": "Publix Store Pulse",
        "genie_configured": genie.is_configured(),
        "lakebase_configured": lakebase.is_configured(),
        "genie_space_id_set": bool(GENIE_SPACE_ID),
        "genie_space_id": GENIE_SPACE_ID or None,
        "genie_embed_url": embed_url,
        "lakebase_reads": lakebase.reads_enabled(),
    }


# --- Store performance reads ---
# Serve from Lakebase Postgres (LTAP) for sub-second reads, falling back to the
# SQL warehouse if the Lakebase copy is unavailable.
def _read(name: str, lake_fn, wh_fn):
    if lakebase.reads_enabled():
        try:
            return lake_fn()
        except Exception:
            log.exception("%s: lakebase read failed, falling back to warehouse", name)
    try:
        return wh_fn()
    except Exception as e:
        log.exception("%s failed", name)
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/metrics/summary")
def metrics_summary():
    return _read("summary", lakebase.summary, warehouse.summary)


@router.get("/metrics/by-store")
def metrics_by_store():
    return _read("by_store", lakebase.by_store, warehouse.by_store)


@router.get("/metrics/by-item")
def metrics_by_item():
    return _read("by_item", lakebase.by_item, warehouse.by_item)


@router.get("/metrics/trend")
def metrics_trend():
    return _read("trend", lakebase.trend, warehouse.trend)


@router.get("/prices")
def prices():
    return _read("prices", lakebase.price_updates, warehouse.price_updates)


@router.get("/catalog")
def catalog():
    def _lake():
        return {"items": lakebase.items_catalog(), "stores": lakebase.stores_catalog()}

    def _wh():
        return {"items": warehouse.items_catalog(), "stores": warehouse.stores_catalog()}

    return _read("catalog", _lake, _wh)


# --- Actions (Lakebase read/write) ---
class ActionIn(BaseModel):
    store_number: str
    item_id: str
    action_type: str
    amount: Optional[float] = None
    note: Optional[str] = None
    created_by: Optional[str] = "workshop-user"


@router.get("/actions")
def list_actions():
    if not lakebase.is_configured():
        return {"configured": False, "actions": []}
    try:
        return {"configured": True, "actions": lakebase.recent_actions()}
    except Exception as e:
        log.exception("list_actions failed")
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/actions")
def create_action(action: ActionIn):
    if not lakebase.is_configured():
        raise HTTPException(status_code=503, detail="Lakebase not configured")
    try:
        row = lakebase.insert_action(
            store_number=action.store_number,
            item_id=action.item_id,
            action_type=action.action_type,
            amount=action.amount,
            note=action.note,
            created_by=action.created_by or "workshop-user",
        )
        return {"configured": True, "action": row}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log.exception("create_action failed")
        raise HTTPException(status_code=502, detail=str(e))


@router.delete("/actions/{action_id}")
def remove_action(action_id: int):
    if not lakebase.is_configured():
        raise HTTPException(status_code=503, detail="Lakebase not configured")
    try:
        deleted = lakebase.delete_action(action_id)
        return {"deleted": deleted}
    except Exception as e:
        log.exception("remove_action failed")
        raise HTTPException(status_code=502, detail=str(e))


# --- Ask Genie ---
class GenieIn(BaseModel):
    question: str


@router.post("/genie/ask")
def genie_ask(payload: GenieIn):
    if not genie.is_configured():
        return {"configured": False}
    try:
        return genie.ask(payload.question)
    except Exception as e:
        log.exception("genie_ask failed")
        raise HTTPException(status_code=502, detail=str(e))
