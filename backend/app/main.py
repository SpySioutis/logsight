"""LogSight backend: FastAPI application entrypoint."""

import logging

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import dashboard, errors, filters, health, imports, logs, traces

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("logsight")

@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
    logger.info("LogSight backend starting")
    yield
    logger.info("LogSight backend stopping")


app = FastAPI(
    title="LogSight API",
    version="0.1.0",
    description="Self-hosted log analysis API: import, search, filter and analyze application logs.",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
app.include_router(imports.router, prefix="/api")
app.include_router(logs.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(errors.router, prefix="/api")
app.include_router(filters.router, prefix="/api")
app.include_router(traces.router, prefix="/api")
