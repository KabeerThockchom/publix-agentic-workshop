"""API routes for Store Pulse."""
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import genie, lakebase, warehouse
from ..config import GENIE_SPACE_ID

log = logging.getLogger("store_pulse")
router = APIRouter(prefix="/api")


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/config")
def config():
    return {
        "app": "Publix Store Pulse",
        "genie_configured": genie.is_configured(),
        "lakebase_configured": lakebase.is_configured(),
        "genie_space_id_set": bool(GENIE_SPACE_ID),
    }


# --- Store performance (warehouse reads) ---
@router.get("/metrics/summary")
def metrics_summary():
    try:
        return warehouse.summary()
    except Exception as e:
        log.exception("summary failed")
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/metrics/by-store")
def metrics_by_store():
    try:
        return warehouse.by_store()
    except Exception as e:
        log.exception("by_store failed")
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/metrics/by-item")
def metrics_by_item():
    try:
        return warehouse.by_item()
    except Exception as e:
        log.exception("by_item failed")
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/metrics/trend")
def metrics_trend():
    try:
        return warehouse.trend()
    except Exception as e:
        log.exception("trend failed")
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/prices")
def prices():
    try:
        return warehouse.price_updates()
    except Exception as e:
        log.exception("prices failed")
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/catalog")
def catalog():
    try:
        return {"items": warehouse.items_catalog(), "stores": warehouse.stores_catalog()}
    except Exception as e:
        log.exception("catalog failed")
        raise HTTPException(status_code=502, detail=str(e))


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
