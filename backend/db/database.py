from sqlalchemy.ext.asyncio import AsyncSession
from backend.models.repository import Repository, Commit, Issue, PullRequest, IssueComment, PullRequestComment
from backend.models.base import Base
from sqlalchemy.ext.asyncio import create_async_engine
from backend.config.settings import settings

async def save_repository(session: AsyncSession, repository: Repository) -> Repository:
    session.add(repository)
    await session.flush()  # This ensures the ID is generated
    await session.refresh(repository)  # This loads the generated ID into our object
    return repository

async def save_commit(session: AsyncSession, commit: Commit) -> Commit:
    session.add(commit)
    return commit

async def save_issue(session: AsyncSession, issue: Issue) -> Issue:
    session.add(issue)
    await session.flush()  # Ensure ID is generated
    await session.refresh(issue)  # Load the generated ID
    return issue

async def save_pull_request(session: AsyncSession, pr: PullRequest) -> PullRequest:
    session.add(pr)
    await session.flush()  # Ensure ID is generated
    await session.refresh(pr)  # Load the generated ID
    return pr

async def save_issue_comment(session: AsyncSession, comment: IssueComment) -> IssueComment:
    session.add(comment)
    return comment

async def save_pr_comment(session: AsyncSession, comment: PullRequestComment) -> PullRequestComment:
    session.add(comment)
    return comment

async def init_db():
    """Initialize the database by creating all tables."""
    engine = create_async_engine(settings.database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
