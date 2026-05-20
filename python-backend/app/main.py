"""
FastAPI主应用
"""
import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import SQLAlchemyError

from app.core.errors import BusinessException, ErrorCode
from app.db.redis import get_redis
from app.db.redis_session import RedisSessionBackend
from app.core.config import get_settings
from app.core.logging_config import LoggingConfig
from app.middleware.session_middleware import RedisSessionMiddleware
from app.api import batch, content_eval, conversation, health, listen_eval, model, oral_combined_eval, oral_gen, rating, scenario, stats, test, unified_eval, user, voice, ws_batch
from app.services.oral_eval.unified_eval_daemon_manager import stop_daemons


settings = get_settings()

LoggingConfig.setup_logging(log_level="DEBUG" if settings.APP_DEBUG else "INFO")

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # startup
    logger.info("=" * 50)
    logger.info("AI 大模型评测平台启动")
    logger.info("应用名称: %s", settings.APP_NAME)
    logger.info("环境：%s", settings.APP_ENV)
    logger.info("端口：%d", settings.APP_PORT)
    logger.info("调试模式：%s", settings.APP_DEBUG)
    if settings.UNIFIED_EVAL_ENABLED:
        import asyncio
        from app.services.oral_eval.unified_eval_daemon_manager import daemons_healthy

        async def _log_daemon_status() -> None:
            if await daemons_healthy():
                logger.info("统一评测 daemon 已就绪")
            else:
                logger.warning(
                    "统一评测 daemon 未就绪；请先执行: bash scripts/eval-daemons.sh start --wait"
                )

        asyncio.create_task(_log_daemon_status())
    from app.services.job_resume import mark_stale_jobs

    marked = await mark_stale_jobs()
    if marked:
        logger.info("已将 %d 个中断任务标记为 interrupted", marked)
    logger.info("=" * 50)
    yield
    # shutdown
    await stop_daemons()
    logger.info("AI 大模型评测平台关闭")


app = FastAPI(
    title=settings.APP_NAME,
    description="AI大模型评测平台 - Python后端",
    version="0.0.1",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS_LIST,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    RedisSessionMiddleware,
    session_backend=RedisSessionBackend(get_redis()),
)


@app.exception_handler(BusinessException)
async def business_exception_handler(request: Request, exc: BusinessException):
    del request
    return JSONResponse(status_code=exc.status_code, content=exc.to_dict())


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    del request
    logger.exception("数据库操作失败: %s", exc)
    return JSONResponse(
        status_code=200,
        content={
            "code": ErrorCode.SYSTEM_ERROR.code,
            "data": None,
            "message": "数据库连接失败，请检查 DB_HOST / DB_PORT / DB_USER / DB_PASSWORD / DB_NAME 配置",
        },
    )


app.include_router(health.router, prefix="/api")
app.include_router(test.router, prefix="/api")
app.include_router(user.router, prefix="/api")
app.include_router(conversation.router, prefix="/api")
app.include_router(model.router, prefix="/api")
app.include_router(rating.router, prefix="/api")
app.include_router(scenario.router, prefix="/api")
app.include_router(batch.router, prefix="/api")
app.include_router(stats.router, prefix="/api")
app.include_router(ws_batch.router, prefix="/api")
app.include_router(voice.router, prefix="/api")
app.include_router(unified_eval.router, prefix="/api")
app.include_router(content_eval.router, prefix="/api")
app.include_router(oral_combined_eval.router, prefix="/api")
app.include_router(listen_eval.router, prefix="/api")
app.include_router(oral_gen.router, prefix="/api")

@app.get("/")
async def root():
    """根路径"""
    logger.info("访问根路径")
    return {
        "message": "Welcome to AI Evaluation Platform",
        "docs": "/api/docs",
        "version": "0.0.1"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.APP_PORT,
        reload=settings.APP_DEBUG
    )
