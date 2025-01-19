from pydantic_settings import BaseSettings
from functools import lru_cache
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

class Settings(BaseSettings):
    # GitHub settings
    github_token: str
    github_api_url: str = "https://api.github.com"
    max_retries: int = 3
    retry_delay: int = 5

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
