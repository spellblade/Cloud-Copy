# FastAPI app: restore cloud sessions on startup and serve the dual-pane UI.

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.config import settings
from app.routers import auth, files, system, transfers
from app.services.mega_client import mega_adapter
from app.services.pikpak_client import pikpak_adapter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("cloud-copy")

STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # On startup, re-login MEGA and PikPak from saved credentials; log shutdown.
    logger.info("Starting Cloud Copy v%s", __version__)
    # Attempt session restore
    try:
        if await mega_adapter.restore_session():
            logger.info("Restored MEGA session for %s", mega_adapter.username)
    except Exception as exc:  # noqa: BLE001
        logger.warning("MEGA restore: %s", exc)
    try:
        if await pikpak_adapter.restore_session():
            logger.info("Restored PikPak session for %s", pikpak_adapter.username)
    except Exception as exc:  # noqa: BLE001
        logger.warning("PikPak restore: %s", exc)
    yield
    logger.info("Shutting down")


app = FastAPI(title=settings.app_name, version=__version__, lifespan=lifespan)

app.include_router(auth.router)
app.include_router(files.router)
app.include_router(transfers.router)
app.include_router(system.router)


@app.get("/api/health")
async def health():
    # Liveness probe used by CI and operators.
    return {"ok": True, "version": __version__}


if STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/")
    async def index():
        # Serve the dual-pane web UI.
        return FileResponse(STATIC_DIR / "index.html")


def run() -> None:
    # Start uvicorn bound to ``settings.host`` / ``settings.port`` (no reload).
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )


if __name__ == "__main__":
    run()
