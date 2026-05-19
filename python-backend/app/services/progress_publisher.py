import json
from typing import Any, Dict, Optional

from app.db.redis import get_redis


class ProgressPublisher:
    @staticmethod
    def channel(job_id: str) -> str:
        return f"batch:progress:{job_id}"

    @staticmethod
    async def publish(job_id: str, payload: Dict[str, Any]) -> None:
        redis = get_redis()
        data = json.dumps(payload, ensure_ascii=False)
        await redis.publish(ProgressPublisher.channel(job_id), data)

    @staticmethod
    async def build_progress_payload(
        job_id: str,
        status: str,
        completed_tasks: int,
        total_tasks: int,
        failed_tasks: int,
        event_type: str = "progress",
        current_model: Optional[str] = None,
        current_item_index: Optional[int] = None,
        phase: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "type": event_type,
            "jobId": job_id,
            "completedTasks": completed_tasks,
            "totalTasks": total_tasks,
            "failedTasks": failed_tasks,
            "currentModel": current_model,
            "currentItemIndex": current_item_index,
            "status": status,
        }
        if phase:
            payload["phase"] = phase
        return payload
