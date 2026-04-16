"""FastAPI entrypoint."""

from __future__ import annotations

import logging
from typing import Dict
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import router
from utils.config import get_settings
from utils.logging import configure_logging

configure_logging(get_settings().log_level)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # 预留：启动时初始化链上客户端、连接池、向量索引等
    logger.info("application startup")
    yield
    # 预留：关闭资源
    logger.info("application shutdown")


app = FastAPI(
    title="Blockchain Wallet Security Analysis Agent (MVP)",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(router)


@app.get("/")
async def root() -> Dict[str, str]:
    return {
        "message": "POST /analyze-wallet (pipeline) or POST /agent/analyze-wallet (LangChain agent)",
        "docs": "/docs",
    }
