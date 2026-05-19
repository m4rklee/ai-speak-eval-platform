import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.db.redis import get_redis
from app.db.redis_session import RedisSessionBackend
from app.db.session import AsyncSessionLocal
from app.models.batch_job import BatchJob
from app.services.batch_job_service import BatchJobService
from app.services.progress_publisher import ProgressPublisher
from app.services.user_service import USER_LOGIN_STATE


router = APIRouter(tags=["WebSocket"])


async def _get_user_id_from_ws(websocket: WebSocket) -> int | None:
    session_id = websocket.cookies.get("session_id")
    if not session_id:
        return None
    redis = get_redis()
    backend = RedisSessionBackend(redis)
    if not await backend.exists(session_id):
        return None
    session_data = await backend.get(session_id)
    if not session_data:
        return None
    user_info = session_data.get(USER_LOGIN_STATE)
    if not user_info or not user_info.get("id"):
        return None
    return int(user_info["id"])


@router.websocket("/ws/batch/{job_id}")
async def batch_progress_ws(websocket: WebSocket, job_id: str):
    await websocket.accept()

    user_id = await _get_user_id_from_ws(websocket)
    if not user_id:
        await websocket.close(code=4401, reason="未登录")
        return

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(BatchJob).where(
                BatchJob.id == job_id,
                BatchJob.user_id == user_id,
                BatchJob.is_delete == 0
            )
        )
        job = result.scalar_one_or_none()
        if not job:
            await websocket.close(code=4404, reason="任务不存在")
            return
        snapshot = await BatchJobService(db).get_job(job_id, user_id)

    await websocket.send_text(json.dumps({
        "type": "snapshot",
        "jobId": job_id,
        "completedTasks": snapshot.completed_tasks,
        "totalTasks": snapshot.total_tasks,
        "failedTasks": snapshot.failed_tasks,
        "status": snapshot.status,
    }, ensure_ascii=False))

    if snapshot.status in ("completed", "failed", "cancelled"):
        await websocket.send_text(json.dumps({
            "type": snapshot.status,
            "jobId": job_id,
            "completedTasks": snapshot.completed_tasks,
            "totalTasks": snapshot.total_tasks,
            "failedTasks": snapshot.failed_tasks,
            "status": snapshot.status,
        }, ensure_ascii=False))
        await websocket.close()
        return

    redis = get_redis()
    pubsub = redis.pubsub()
    channel = ProgressPublisher.channel(job_id)
    await pubsub.subscribe(channel)

    try:
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message and message.get("type") == "message":
                data = message.get("data")
                if isinstance(data, bytes):
                    data = data.decode("utf-8")
                await websocket.send_text(data)
                try:
                    payload = json.loads(data)
                    if payload.get("type") in ("completed", "failed", "cancelled"):
                        break
                except json.JSONDecodeError:
                    pass
            await asyncio.sleep(0.05)
    except WebSocketDisconnect:
        pass
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.close()
