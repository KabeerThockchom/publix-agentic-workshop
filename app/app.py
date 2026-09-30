"""Publix Store Pulse - FastAPI entry point.

Serves the JSON API under /api and the built React SPA (frontend/dist) at root.
"""
import logging
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from server.routes.api import router as api_router

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Publix Store Pulse")
app.include_router(api_router)

_DIST = Path(__file__).parent / "frontend" / "dist"


if _DIST.exists():
    app.mount("/assets", StaticFiles(directory=_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}")
    def serve_spa(full_path: str):
        if full_path.startswith("api/"):
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        candidate = _DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_DIST / "index.html")
else:

    @app.get("/")
    def missing_build():
        return {"detail": "frontend/dist not built"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
