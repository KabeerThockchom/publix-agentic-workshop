"""Ask Genie via the Genie Conversations REST API.

Degrades gracefully when GENIE_SPACE_ID is unset (a space is provisioned
separately). The panel then shows a "configure GENIE_SPACE_ID" state.
"""
import time
from typing import Any

import requests

from .config import GENIE_SPACE_ID, get_oauth_token, get_workspace_host

_TERMINAL_OK = {"COMPLETED"}
_TERMINAL_BAD = {"FAILED", "CANCELLED", "QUERY_RESULT_EXPIRED"}


def is_configured() -> bool:
    return bool(GENIE_SPACE_ID)


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {get_oauth_token()}",
        "Content-Type": "application/json",
    }


def _base() -> str:
    return f"{get_workspace_host()}/api/2.0/genie/spaces/{GENIE_SPACE_ID}"


def ask(question: str, timeout_s: int = 90) -> dict[str, Any]:
    if not is_configured():
        return {"configured": False}

    headers = _headers()
    base = _base()

    start = requests.post(
        f"{base}/start-conversation",
        headers=headers,
        json={"content": question},
        timeout=30,
    )
    start.raise_for_status()
    body = start.json()
    conversation_id = body.get("conversation_id") or body.get("conversation", {}).get("id")
    message_id = body.get("message_id") or body.get("message", {}).get("id")

    deadline = time.time() + timeout_s
    message: dict[str, Any] = {}
    while time.time() < deadline:
        resp = requests.get(
            f"{base}/conversations/{conversation_id}/messages/{message_id}",
            headers=headers,
            timeout=30,
        )
        resp.raise_for_status()
        message = resp.json()
        status = message.get("status")
        if status in _TERMINAL_OK:
            break
        if status in _TERMINAL_BAD:
            return {"configured": True, "error": f"Genie status: {status}"}
        time.sleep(1.5)
    else:
        return {"configured": True, "error": "Genie timed out"}

    answer_text = None
    sql = None
    columns: list[str] = []
    rows: list[list[Any]] = []

    for att in message.get("attachments", []) or []:
        text = att.get("text")
        if text and text.get("content"):
            answer_text = text["content"]
        query = att.get("query")
        if query:
            sql = query.get("query")
            if not answer_text and query.get("description"):
                answer_text = query["description"]
            att_id = att.get("attachment_id")
            if att_id:
                cols, data = _fetch_query_result(base, conversation_id, message_id, att_id, headers)
                columns, rows = cols, data

    return {
        "configured": True,
        "answer": answer_text or message.get("content"),
        "sql": sql,
        "columns": columns,
        "rows": rows,
    }


def _fetch_query_result(base, conversation_id, message_id, attachment_id, headers):
    try:
        resp = requests.get(
            f"{base}/conversations/{conversation_id}/messages/{message_id}"
            f"/attachments/{attachment_id}/query-result",
            headers=headers,
            timeout=60,
        )
        resp.raise_for_status()
        payload = resp.json()
        sr = payload.get("statement_response") or payload.get("query_result") or {}
        manifest = sr.get("manifest", {}) or {}
        schema = manifest.get("schema", {}) or {}
        cols = [c.get("name") for c in schema.get("columns", [])]
        result = sr.get("result", {}) or {}
        data = result.get("data_array") or []
        return cols, data[:200]
    except Exception:
        return [], []
