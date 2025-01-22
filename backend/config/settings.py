from pydantic_settings import BaseSettings
from functools import lru_cache
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

class Settings(BaseSettings):
    # GitHub settings
    github_token: str
    github_api_url: str = "https://api.github.com"
    max_retries: int = 3
    retry_delay: int = 8
    success_delay: int = 1

    # Database settings
    db_host: str = "localhost"
    db_port: int = 5432
    db_user: str = "developer"
    db_password: str = "devpassword"
    db_name: str = "githubxplainer"

    @property
    def database_url(self) -> str:
        return f"postgresql+asyncpg://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

    # API settings
    api_port: int = 8000
    api_host: str = "0.0.0.0"
    debug: bool = True

    # Scheduler settings
    repository_update_interval: int = 5
    use_scheduler: bool = True

    # Redis settings
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str | None = None  # None for local development

    LLM_README_SUMMARIZER: str = "deepseek-r1:8b"
    LLM_DIFF_SUMMARIZER: str = "deepseek-r1:8b"
    LLM_CHUNK_SUMMARIZER: str = "deepseek-r1:14b-qwen-distill-q4_K_M"

    class Config:
        env_file = ".env"

@lru_cache()
def get_settings() -> Settings:
    return Settings()

settings = get_settings()

# SQLAlchemy async engine
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    future=True
)

async_session = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session
