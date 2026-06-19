from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import public_router, router
from app.config import get_settings


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Validate configuration at startup (fail fast).
    get_settings()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Lead Gen Workflow",
        description="Stage 1 — DEFINE: client onboarding and ICP configuration",
        version="0.1.0",
        lifespan=lifespan,
        debug=settings.debug,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(public_router)
    app.include_router(router)
    return app


app = create_app()
