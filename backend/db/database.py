from sqlalchemy.ext.asyncio import AsyncSession
from backend.models.repository import Repository, Commit, Issue, PullRequest
from backend.models.base import Base
from sqlalchemy.ext.asyncio import create_async_engine
from backend.config.settings import settings

async def save_repository(session: AsyncSession, repo: Repository) -> None:
    async with session.begin():
        await session.merge(repo)

async def save_commit(session: AsyncSession, commit: Commit) -> None:
    async with session.begin():
        session.add(commit)
        await session.flush()

async def save_issue(session: AsyncSession, issue: Issue) -> None:
    async with session.begin():
        await session.merge(issue)

async def save_pull_request(session: AsyncSession, pr: PullRequest) -> None:
    async with session.begin():
        await session.merge(pr)

async def init_db():
    """Initialize the database by creating all tables."""
    engine = create_async_engine(settings.database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
