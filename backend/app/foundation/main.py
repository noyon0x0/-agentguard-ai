"""AgentGuard foundation app; explicitly has no signing or broadcast capability."""

from __future__ import annotations

from contextlib import asynccontextmanager
import threading
import logging
import re
import uuid
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

from .config import Settings
from .dashboard_routes import router as dashboard_router
from .database import create_database_engine, create_session_factory
from .errors import install_error_handlers
from .logging_config import configure_logging
from .migrations import upgrade_schema
from .models import Base
from .near_client import NearTestnetClient
from .near_routes import create_near_router
from .near_experiment import router as near_experiment_router
from .routes import router
from .security_engine import ensure_default_policy
from .simulation_lab import router as simulation_router

logger = logging.getLogger("agentguard.api")


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or Settings.from_environment()
    configure_logging(config.log_level)
    engine = create_database_engine(config.database_url)
    near_client = NearTestnetClient(
        rpc_url=config.near_testnet_rpc_url,
        timeout_seconds=config.near_rpc_timeout_seconds,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        Base.metadata.create_all(bind=engine)
        upgrade_schema(engine)
        with app.state.session_factory() as session:
            ensure_default_policy(session)
        yield
        engine.dispose()

    app = FastAPI(
        title=config.app_name,
        description=(
            "AgentGuard AI NEAR Hackathon 2026 edition. Normal evaluation intake never signs or executes. "
            "A separate admin-protected Testnet experiment is disabled unless explicitly configured."
        ),
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )
    app.state.session_factory = create_session_factory(engine)
    app.state.database_engine = engine
    app.state.settings = config
    app.state.security_lock = threading.RLock()
    app.state.near_client = near_client

    @app.middleware("http")
    async def safe_request_logging(request, call_next):
        supplied_id = request.headers.get("x-request-id", "")
        request_id = supplied_id if re.fullmatch(r"[A-Za-z0-9._:-]{1,64}", supplied_id) else str(uuid.uuid4())
        request.state.request_id = request_id
        try:
            response = await call_next(request)
        except Exception as exc:
            logger.error("request_failed", extra={"method": request.method, "error_type": type(exc).__name__, "request_id": request_id})
            raise
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "request_completed",
            extra={"method": request.method, "status_code": response.status_code, "request_id": request_id},
        )
        return response

    app.include_router(router)
    app.include_router(dashboard_router)
    app.include_router(simulation_router)
    app.include_router(create_near_router(near_client))
    app.include_router(near_experiment_router)

    dashboard_file = Path(__file__).resolve().parents[3] / "frontend" / "dashboard.html"

    @app.get("/", include_in_schema=False)
    @app.get("/dashboard", include_in_schema=False)
    def serve_dashboard():
        if not dashboard_file.is_file():
            raise HTTPException(status_code=404, detail={"code": "DASHBOARD_NOT_FOUND"})
        html = dashboard_file.read_text(encoding="utf-8")
        return HTMLResponse(content=html)

    install_error_handlers(app)
    return app


app = create_app()
