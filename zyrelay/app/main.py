from __future__ import annotations

import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from zyrelay import __version__
from zyrelay.app.api.routes_documents import router as documents_router
from zyrelay.app.api.routes_search import router as search_router
from zyrelay.app.api.routes_conventions import router as conventions_router
from zyrelay.app.api.routes_plugins import router as plugins_router
from zyrelay.app.core.config import Settings
from zyrelay.app.core.exceptions import ZYRelayError
from zyrelay.app.core.logging import configure_logging
from zyrelay.app.services import DocumentService
from zyrelay.plugin import DocIntelligencePlugin, PluginRegistry
from zyrelay.plugin.dependencies import create_default_dependencies
from zyrelay.relay import RelayService
from zyrelay.app.api.routes_relay import router as relay_router


def create_app(settings: Settings | None = None) -> FastAPI:
    configure_logging()
    settings = settings or Settings.from_env()
    app = FastAPI(
        title="ZYRelay DocIntelligence",
        version=__version__,
        description="Rule-first PDF/DOCX semantic indexing MVP",
    )
    document_service = DocumentService(settings)
    app.state.document_service = document_service
    registry = PluginRegistry()
    registry.register(
        DocIntelligencePlugin(
            create_default_dependencies(
                settings=settings,
                document_service=document_service,
            )
        )
    )
    app.state.plugin_registry = registry
    app.state.relay_service = RelayService(settings)

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request.state.request_id = request.headers.get(
            "x-request-id", f"REQ-{uuid.uuid4().hex[:16].upper()}"
        )
        response = await call_next(request)
        response.headers["x-request-id"] = request.state.request_id
        return response

    @app.exception_handler(ZYRelayError)
    async def zyrelay_error_handler(request: Request, exc: ZYRelayError):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error_code": exc.error_code,
                "message": exc.message,
                "details": exc.details,
                "request_id": request.state.request_id,
            },
        )

    @app.get("/health", tags=["system"])
    def health():
        return {"status": "ok", "service": "zyrelay-docintelligence", "version": __version__}

    app.include_router(documents_router)
    app.include_router(search_router)
    app.include_router(conventions_router)
    app.include_router(plugins_router)
    app.include_router(relay_router)
    return app


app = create_app()
