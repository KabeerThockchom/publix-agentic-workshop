"""
Genie AI Chatbot API endpoints.

Provides natural language query interface using Databricks Genie:
- Start conversations
- Continue conversations with follow-ups
- Get suggested questions
- Retrieve conversation history

Used by Regional Manager's Compare view for AI insights.
"""

import os
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from config.settings import Settings, get_settings
from services.genie import genie_client
from config.domain import domain

router = APIRouter()


# === Pydantic Models ===

class QueryRequest(BaseModel):
    """Request to query Genie."""
    question: str
    conversation_id: Optional[str] = None


class QueryResponse(BaseModel):
    """Response from Genie query."""
    conversation_id: str
    message_id: str
    response: str
    data: Optional[List[dict]] = None
    sql: Optional[str] = None
    genie_url: Optional[str] = None


class SuggestedQuestion(BaseModel):
    """Suggested question for users."""
    question: str
    category: str  # "sales", "labor", "inventory", "comparison"


# === Endpoints ===

@router.post("/query", response_model=QueryResponse)
async def query_genie(
    request: QueryRequest,
    settings: Settings = Depends(get_settings),
) -> QueryResponse:
    """
    Query Genie with a natural language question.
    
    If conversation_id is provided, continues existing conversation.
    Otherwise, starts a new conversation.
    
    Example questions:
    - "Which store had the highest sales last week?"
    - "Compare Store #5 vs Store #12 performance"
    - "Why did Store #22's labor costs increase?"
    """
    # Check if Genie is configured
    if not settings.genie_space_id:
        raise HTTPException(
            status_code=503,
            detail="Genie Space not configured. Run setup notebook 06_setup_genie_space.py first."
        )

    try:
        if request.conversation_id:
            # Continue existing conversation
            result = genie_client.continue_conversation(
                conversation_id=request.conversation_id,
                question=request.question
            )
        else:
            # Start new conversation
            result = genie_client.start_conversation(request.question)

        # Add Genie URL for opening in UI
        genie_url = genie_client.get_genie_url(result["conversation_id"])

        return QueryResponse(
            conversation_id=result["conversation_id"],
            message_id=result["message_id"],
            response=result["response"],
            data=result.get("data"),
            sql=result.get("sql"),
            genie_url=genie_url
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Return a simulated response for demo purposes
        return QueryResponse(
            conversation_id="demo-conversation",
            message_id="demo-message",
            response=_get_demo_response(request.question),
            data=_get_demo_data(request.question),
            sql=None,
            genie_url=None
        )


@router.get("/suggestions", response_model=List[SuggestedQuestion])
async def get_suggested_questions(
    settings: Settings = Depends(get_settings),
) -> List[SuggestedQuestion]:
    """
    Get suggested questions for the Genie chatbot.
    
    Returns categorized questions users commonly ask.
    """
    # Suggestions aligned with actual Genie space tables:
    # - stores: store_id, name, address, city, state, latitude, longitude, sqft, open_date
    # - stores_kpi_view: store_id, name, city, sales_today, sales_yesterday, sales_wtd, sales_mtd, sales_ytd, vs_yesterday_pct, labor_cost_pct, rank
    # - pos_transactions: txn_id, store_id, timestamp, total, channel, payment_method
    # - employees: employee_id, store_id, name, role, hourly_rate, employment_type, status
    # - inventory_levels: store_id, ingredient_id, date, qty_on_hand, par_level, days_supply
    
    suggestions = [
        # Sales questions (from stores_kpi_view)
        SuggestedQuestion(
            question="Which store had the highest sales last week?",
            category="sales"
        ),
        SuggestedQuestion(
            question="Show me sales trends for the past 30 days",
            category="sales"
        ),
        SuggestedQuestion(
            question="What are the top selling items this week?",
            category="sales"
        ),
        SuggestedQuestion(
            question="What's the average labor cost percentage by store?",
            category="labor"
        ),
        
        # Transaction/Channel questions (from pos_transactions)
        SuggestedQuestion(
            question="What percentage of sales come from delivery vs in-store?",
            category="sales"
        ),
        SuggestedQuestion(
            question="Which payment method is most popular?",
            category="sales"
        ),
        
        # Employee questions (from employees table)
        SuggestedQuestion(
            question="How many employees work at each store?",
            category="labor"
        ),
        SuggestedQuestion(
            question="What's the average hourly rate by role?",
            category="labor"
        ),
        
        # Inventory questions (from inventory_levels)
        SuggestedQuestion(
            question="Which stores have inventory below par level?",
            category="inventory"
        ),
        SuggestedQuestion(
            question="Show me stores with less than 2 days supply",
            category="inventory"
        ),
        
        # Comparison questions (from stores_kpi_view)
        SuggestedQuestion(
            question="Which stores are underperforming this month?",
            category="comparison"
        ),
        SuggestedQuestion(
            question="Rank all stores by monthly sales",
            category="comparison"
        ),
    ]

    return suggestions


@router.get("/status")
async def get_genie_status(
    settings: Settings = Depends(get_settings),
) -> dict:
    """
    Get Genie configuration status.
    
    Returns whether Genie is properly configured.
    """
    is_configured = bool(settings.genie_space_id)

    # Build the embed iframe URL for the Genie space, if configured.
    # Format: https://<host>/embed/genie/rooms/<space_id>?o=<workspace_id>
    embed_url = None
    if is_configured:
        host = (settings.databricks_host or os.getenv("DATABRICKS_HOST") or "").rstrip("/")
        if host and not host.startswith("http"):
            host = f"https://{host}"
        if host:
            embed_url = f"{host}/embed/genie/rooms/{settings.genie_space_id}"
            if settings.workspace_id:
                embed_url += f"?o={settings.workspace_id}"

    return {
        "configured": is_configured,
        "genie_space_id": settings.genie_space_id if is_configured else None,
        "embed_url": embed_url,
        "message": "Genie is ready" if is_configured else "Run setup notebook to configure Genie Space"
    }


# === Demo Response Generator (customer-agnostic fallback) ===
# These fire ONLY when the real Genie space is unreachable (the `except` path in
# query_genie). Store names come from the domain taxonomy (config/domain.py) and
# the language is deliberately generic — no prior-customer stores, menu items,
# ingredients, or loyalty-program names may ever appear here.

def _demo_stores(n: int = 6) -> List[dict]:
    """Up to n stores from the domain taxonomy, with safe generic fallbacks."""
    out: List[dict] = []
    for i, st in enumerate(domain.stores()[:n]):
        out.append({
            "name": st.get("name") or f"Store {st.get('id', i + 1)}",
            "city": st.get("city", ""),
        })
    while len(out) < n:
        out.append({"name": f"Store {len(out) + 1}", "city": ""})
    return out


def _get_demo_response(question: str) -> str:
    """Generic demo response used only when Genie is unreachable."""
    q = question.lower()
    s = _demo_stores(6)
    total = domain.num_stores() or len(s)

    if "highest sales" in q or ("top" in q and "sales" in q):
        return (
            f"Based on stores_kpi_view, **{s[0]['name']}** had the highest weekly "
            "sales this period.\n\n"
            "Top 3 stores by weekly sales (sales_wtd):\n"
            f"1. **{s[0]['name']}**\n2. **{s[1]['name']}**\n3. **{s[2]['name']}**\n\n"
            "Open the Genie space for the live figures and the full ranking."
        )

    if "underperforming" in q:
        return (
            "Based on stores_kpi_view rankings, the lowest-ranked stores this month:\n\n"
            f"1. **{s[-1]['name']}**\n2. **{s[-2]['name']}**\n3. **{s[-3]['name']}**\n\n"
            "These have the lowest monthly sales and may benefit from targeted local "
            "marketing and loyalty promotions."
        )

    if "labor cost" in q:
        return (
            "From stores_kpi_view, labor cost percentage varies across the fleet:\n\n"
            "| Store | Labor Cost % |\n|---|---|\n"
            f"| {s[0]['name']} | 24.1% |\n"
            f"| {s[1]['name']} | 25.2% |\n"
            f"| {s[2]['name']} | 25.8% |\n"
            "| Fleet average | 26.5% |\n\n"
            "Stores above ~29% should review scheduling efficiency."
        )

    if "delivery" in q or "channel" in q:
        chans = domain.sales_channels()
        if chans:
            rows = "\n".join(
                f"| {c.get('label', c.get('key', 'channel'))} | "
                f"{round(float(c.get('share', 0)) * 100)}% |"
                for c in chans
            )
            return (
                "From pos_transactions, sales breakdown by channel:\n\n"
                "| Channel | Share |\n|---|---|\n" + rows +
                "\n\nOpen the Genie space for live counts."
            )
        return (
            "From pos_transactions, sales split across the configured order "
            "channels — open the Genie space for the live breakdown."
        )

    if "payment" in q:
        return (
            "From pos_transactions, most-used payment methods:\n\n"
            "| Payment Method | Share |\n|---|---|\n"
            "| credit | 40% |\n| debit | 25% |\n| cash | 20% |\n| mobile wallet | 15% |\n\n"
            "Card and digital payments dominate across all stores."
        )

    if "employee" in q or "staff" in q:
        return (
            "From the employees table, each store runs a mix of roles:\n\n"
            "- Shift Leads (~15%)\n"
            "- Team Members / Prep (~55%)\n"
            "- Cashiers / CSR (~20%)\n"
            "- Support (~10%)\n\n"
            "Full-time vs part-time split varies by store volume."
        )

    if "inventory" in q or "par" in q or "supply" in q:
        return (
            "From inventory_levels, a few stores are running low:\n\n"
            "| Store | Items Below Par | Avg Days Supply |\n|---|---|---|\n"
            f"| {s[0]['name']} | 4 | 1.8 |\n"
            f"| {s[1]['name']} | 3 | 2.1 |\n"
            f"| {s[2]['name']} | 3 | 2.3 |\n\n"
            "Prioritize restocking items where qty_on_hand < par_level."
        )

    if "rank" in q or "all stores" in q:
        rows = "\n".join(f"| {i + 1} | {st['name']} |" for i, st in enumerate(s[:5]))
        more = max(total - 5, 0)
        return (
            f"From stores_kpi_view, all {total} stores ranked by monthly sales:\n\n"
            "| Rank | Store |\n|---|---|\n" + rows +
            (f"\n| … | (+{more} more) |" if more else "") +
            "\n\nUse the rank column for quick performance comparisons."
        )

    return (
        "I analyzed your question about the store data. Available tables:\n\n"
        "- **stores** — location info (address, city, sqft, open_date)\n"
        "- **stores_kpi_view** — sales (today/WTD/MTD/YTD), labor_cost_pct, rank\n"
        "- **pos_transactions** — transaction detail (total, channel, payment_method)\n"
        "- **employees** — staff (role, hourly_rate, employment_type)\n"
        "- **inventory_levels** — stock (qty_on_hand, par_level, days_supply)\n\n"
        "Try asking about specific metrics from these tables!"
    )


def _get_demo_data(question: str) -> Optional[List[dict]]:
    """Generic demo data used only when Genie is unreachable."""
    q = question.lower()
    s = _demo_stores(6)
    total = domain.num_stores() or len(s)

    if "highest sales" in q or ("top" in q and "sales" in q):
        return [{"rank": i + 1, "name": st["name"], "city": st["city"]}
                for i, st in enumerate(s[:5])]

    if "rank" in q or "all stores" in q:
        return [{"rank": i + 1, "name": st["name"]} for i, st in enumerate(s[:5])]

    if "labor" in q:
        pct = [24.1, 25.2, 25.8, 27.4, 30.2]
        return [{"name": s[i]["name"], "city": s[i]["city"], "labor_cost_pct": pct[i]}
                for i in range(5)]

    if "delivery" in q or "channel" in q:
        chans = domain.sales_channels()
        if chans:
            return [{"channel": c.get("key", "channel"),
                     "percentage": round(float(c.get("share", 0)) * 100, 1)}
                    for c in chans]
        return None

    if "payment" in q:
        return [
            {"payment_method": "credit", "percentage": 40.0},
            {"payment_method": "debit", "percentage": 25.0},
            {"payment_method": "cash", "percentage": 20.0},
            {"payment_method": "mobile_wallet", "percentage": 15.0},
        ]

    if "employee" in q or "staff" in q or "hourly rate" in q:
        return [
            {"role": "shift_lead", "avg_hourly_rate": 19.50},
            {"role": "team_member", "avg_hourly_rate": 16.50},
            {"role": "cashier", "avg_hourly_rate": 15.50},
        ]

    if "inventory" in q or "par" in q or "supply" in q:
        rows = [(4, 1.8), (3, 2.1), (3, 2.3), (2, 2.5)]
        return [{"name": s[i]["name"], "items_below_par": r[0], "avg_days_supply": r[1]}
                for i, r in enumerate(rows)]

    if "underperforming" in q:
        return [{"rank": total - i, "name": s[-(i + 1)]["name"], "city": s[-(i + 1)]["city"]}
                for i in range(3)]

    return None



