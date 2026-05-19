"""
健康检查接口
"""
import logging

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.db.redis import get_redis
from app.services.oral_eval import unified_eval_daemon_manager as daemon_mgr
from app.services.oral_eval.unified_eval_runner import validate_unified_eval_paths

router = APIRouter(prefix="/health", tags=["Health"])
logger = logging.getLogger(__name__)


@router.get("")
async def health_check():
    """健康检查接口"""
    logger.info("健康检查")
    return {
        "status": "ok",
        "message": "AI Evaluation Platform is running."
    }

@router.get("/db")
async def db_health_check(db: Session = Depends(get_db)):
    """数据库健康检查"""
    try:
        db.execute(text("SELECT 1"))
        logger.info("数据库连接正常")
        return {
            "status": "ok",
            "message": "Database connection is healthy."
        }
    except Exception as e:
        logger.error("数据库连接失败：%s", str(e))
        return {
            "status": "error",
            "message": f"Database connection failed: {str(e)}"
        }
    
@router.get("/redis")
async def redis_health_check():
    """Redis健康检查"""
    try:
        redis = get_redis()
        redis.ping()
        logger.info("Redis连接正常")
        return {
            "status": "ok",
            "message": "Redis conenction is healthy."
        }
    except Exception as e:
        logger.error("Redis连接失败: %s", str(e))
        return {
            "status": "error",
            "message": f"Redis connection failed: {str(e)}"
        }


@router.get("/unified-eval")
async def unified_eval_health():
    """统一语音评测（MultiPA + APG-MOS）常驻服务状态"""
    settings = get_settings()
    paths_ok, paths_msg = validate_unified_eval_paths()
    daemon_ok = await daemon_mgr.daemons_healthy()
    daemon_managed = daemon_mgr.daemons_running()
    paths_message = paths_msg
    if paths_ok and not daemon_ok:
        paths_message = (
            f"{paths_msg}; " if paths_msg else ""
        ) + "评测 daemon 未就绪，请执行 bash scripts/eval-daemons.sh restart"
    return {
        "unified_eval_enabled": settings.UNIFIED_EVAL_ENABLED,
        "use_daemon": True,
        "paths_ok": paths_ok,
        "paths_message": paths_message,
        "daemon_running": daemon_managed or daemon_ok,
        "daemon_ready": daemon_ok,
        "multipa_port": settings.MULTIPA_DAEMON_PORT,
        "apg_port": settings.APG_DAEMON_PORT,
        "engine": "daemon",
    }
