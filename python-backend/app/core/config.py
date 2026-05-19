"""
配置管理模块
"""
from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    """应用配置类"""

    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_USER: str = "root"
    DB_PASSWORD: str = "11111111"
    DB_NAME: str = "ai_eval"

    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: str = ""

    OPENROUTER_API_KEY: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    # OpenRouter 专用 HTTP 代理（空字符串表示不走代理）
    OPENROUTER_HTTP_PROXY: str = "http://127.0.0.1:7890"

    AIHUBMIX_API_KEY: str = ""
    # 对话接口 base（OpenAI SDK）：https://aihubmix.com/v1
    AIHUBMIX_BASE_URL: str = "https://aihubmix.com/v1"
    # 模型列表接口（可选）：https://aihubmix.com/api/v1
    AIHUBMIX_MODELS_URL: str = "https://aihubmix.com/api/v1"

    APP_NAME: str = "AI Evaluation Platform"
    APP_ENV: str = "local"
    APP_DEBUG: bool = True
    APP_PORT: int = 8123
    SECRET_KEY: str

    SESSION_EXPIRE_SECONDS: int = 2592000
    COOKIE_MAX_AGE: int = 2592000

    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:8080"

    PRONUNCIATION_EVAL_URL: str = ""
    ORAL_EVAL_JUDGE_MODEL: str = "aihubmix:gemini-3.1-flash-lite"
    ORAL_EVAL_DEFAULT_SYSTEM_PROMPT: str = ""

    # 统一语音评测（MultiPA + APG-MOS 常驻 daemon）
    UNIFIED_EVAL_ENABLED: bool = True
    UNIFIED_EVAL_DIR: str = "/root/unified-speech-eval"
    MULTIPA_DIR: str = "/root/my_image_files/口语练习评测/MultiPA"
    APG_MOS_DIR: str = "/root/autodl-tmp/APG-MOS"
    MULTIPA_PYTHON: str = ""
    UNIFIED_EVAL_TIMEOUT_SEC: int = 3600
    # 启动时拉起 MultiPA/APG 常驻进程（模型只加载一次，评测仅走 daemon）
    MULTIPA_DAEMON_PORT: int = 18765
    APG_DAEMON_PORT: int = 18766
    UNIFIED_EVAL_DAEMON_WARMUP_SEC: int = 600
    # daemon 模式下 MultiPA 与 APG-MOS 并行请求（独立进程，可缩短总耗时）
    UNIFIED_EVAL_PARALLEL_DAEMON: bool = True
    UNIFIED_EVAL_MAX_MODELS_PER_JOB: int = 10

    # 内容评测内置题库目录（空则使用 my_version/data/questiontext）
    CONTENT_EVAL_QUESTION_DIR: str = ""
    CONTENT_EVAL_MAX_FILES_PER_JOB: int = 200

    # 北极星 2201 听力评测包目录
    LISTEN_EVAL_PACKAGE_DIR: str = ""
    LISTEN_EVAL_MAX_SAMPLES_PER_JOB: int = 2201
    LISTEN_EVAL_REQUEST_INTERVAL_SEC: float = 1.0
    LISTEN_EVAL_JOB_WORKERS: int = 1

    @property
    def content_eval_question_dir(self) -> str:
        import os
        if self.CONTENT_EVAL_QUESTION_DIR.strip():
            return os.path.abspath(self.CONTENT_EVAL_QUESTION_DIR.strip())
        base = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        return os.path.join(base, "data", "questiontext")

    @property
    def listen_eval_package_dir(self) -> str:
        import os

        if self.LISTEN_EVAL_PACKAGE_DIR.strip():
            return os.path.abspath(self.LISTEN_EVAL_PACKAGE_DIR.strip())
        return os.path.abspath("/root/autodl-tmp/listen_eval/北极星2201评测包")

    @property
    def multipa_python_path(self) -> str:
        if self.MULTIPA_PYTHON.strip():
            return self.MULTIPA_PYTHON.strip()
        import os
        return os.path.join(self.MULTIPA_DIR, ".venv", "bin", "python")

    @property
    def DATABASE_URL(self) -> str:
        """构建数据库连接URL"""
        return f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    @property
    def ASYNC_DATABASE_URL(self) -> str:
        """构建异步数据库连接URL"""
        return f"mysql+asyncmy://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
    
    @property
    def CORS_ORIGINS_LIST(self) -> list[str]:
        """解析CORS允许的源"""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"

@lru_cache()
def get_settings() -> Settings:
    """获取配置实例（单例模式）"""
    return Settings()

