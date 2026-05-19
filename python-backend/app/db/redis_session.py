import json
import uuid
from typing import Dict, Optional

from redis.asyncio import Redis

from app.core.config import get_settings


settings = get_settings()


class RedisSessionBackend:
    """
    Redis Session后端存储
    """
    def __init__(self, redis_client: Redis):
        self.redis = redis_client
        self.prefix = "session:"
        self.expire = settings.SESSION_EXPIRE_SECONDS
    
    async def get(self, session_id: str) -> Optional[Dict]:
        data = await self.redis.get(f"{self.prefix}{session_id}")
        return json.loads(data) if data else None
    
    async def set(self, session_id: str, data: Dict) -> None:
        await self.redis.setex(
            f"{self.prefix}{session_id}",
            self.expire,
            json.dumps(data)
        )

    async def exists(self, session_id: str) -> bool:
        return await self.redis.exists(f"{self.prefix}{session_id}") > 0

    def generate_session_id(self) -> str:
        return str(uuid.uuid4())
    
