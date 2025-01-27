from typing import Optional, Dict, List
from sqlalchemy.ext.asyncio import AsyncSession
from backend.models.repository import Repository, Commit, Issue, IssueComment, CommitDiff, DeletedIssue, RepositoryLanguage, PullRequestSummary
from backend.models.base import Base
from sqlalchemy.ext.asyncio import create_async_engine
from backend.config.settings import settings
from sqlalchemy import select, func, and_, exists, alias, text
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timezone

# Create SQLAlchemy engine for sync operations (Celery tasks)
sync_engine = create_engine(
    settings.database_url.replace("+asyncpg", ""),
    echo=settings.debug
)

# Session factory for synchronous operations
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=sync_engine
)

async def save_repository(session: AsyncSession, repository: Repository) -> Repository:
    session.add(repository)
    await session.flush()  # This ensures the ID is generated
    await session.refresh(repository)  # This loads the generated ID into our object
    return repository

async def save_commit(session: AsyncSession, commit: Commit) -> Commit:
    session.add(commit)
    await session.flush()  # Ensure ID is generated
    await session.refresh(commit)  # Load the generated ID
    return commit

async def save_issue(session: AsyncSession, issue: Issue) -> Issue:
    session.add(issue)
    await session.flush()  # Ensure ID is generated
    await session.refresh(issue)  # Load the generated ID
    return issue

async def save_deleted_issue(session: AsyncSession, deleted_issue: DeletedIssue) -> DeletedIssue:
    session.add(deleted_issue)
    return deleted_issue

async def save_issue_comment(session: AsyncSession, comment: IssueComment) -> IssueComment:
    session.add(comment)
    return comment

async def save_commit_diff(session: AsyncSession, diff: CommitDiff) -> CommitDiff:
    session.add(diff)
    return diff

async def update_repository_attributes(session: AsyncSession, repository_id: int, **kwargs) -> Repository:
    """Update repository attributes by id."""
    result = await session.execute(
        select(Repository).where(Repository.id == repository_id)
    )
    repository = result.scalar_one_or_none()
    if repository:
        for key, value in kwargs.items():
            setattr(repository, key, value)
        await session.flush()
    return repository

async def update_commit_attributes(session: AsyncSession, commit_id: int, **kwargs) -> Commit:
    """Update commit attributes by id."""
    result = await session.execute(
        select(Commit).where(Commit.id == commit_id)
    )
    commit = result.scalar_one_or_none()
    if commit:
        for key, value in kwargs.items():
            setattr(commit, key, value)
        await session.flush()
    return commit


async def init_db():
    """Initialize the database by creating all tables."""
    engine = create_async_engine(settings.database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_last_commit_with_null_parent(session: AsyncSession, repository_id: int) -> Optional[Commit]:
    """Get the most recent commit that has parent_sha == null."""
    result = await session.execute(
        select(Commit)
        .where(and_(
            Commit.repository_id == repository_id,
            Commit.parent_sha == None
        ))
        .order_by(Commit.committed_date.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()

async def get_commit_by_sha(session: AsyncSession, sha: str, repository_id: int) -> Optional[Commit]:
    """Get commit by its SHA."""
    result = await session.execute(
        select(Commit)
        .where(and_(
            Commit.github_sha == sha,
            Commit.repository_id == repository_id
        ))
    )
    return result.scalar_one_or_none()

async def get_last_issue_with_null_parent(session: AsyncSession, repository_id: int) -> Optional[Issue]:
    """Get the most recent issue where the previous issue number doesn't exist in both Issue and DeletedIssue tables."""
    issue_alias = alias(Issue)
    deleted_issue_alias = alias(DeletedIssue)
    subq = (
        select(func.max(Issue.number))
        .where(and_(
            Issue.repository_id == repository_id,
            ~exists(
                select(1)
                .where(and_(
                    issue_alias.c.repository_id == Issue.repository_id,
                    issue_alias.c.number == Issue.number - 1
                ))
            ),
            ~exists(
                select(1)
                .where(and_(
                    deleted_issue_alias.c.repository_id == Issue.repository_id,
                    deleted_issue_alias.c.number == Issue.number - 1
                ))
            )
        ))
    ).scalar_subquery()

    result = await session.execute(
        select(Issue)
        .where(and_(
            Issue.repository_id == repository_id,
            Issue.number == subq
        ))
    )
    return result.scalar_one_or_none()
    
async def get_issue_by_number(session: AsyncSession, number: int, repository_id: int) -> Optional[Issue]:
    """Get issue by its number."""
    result = await session.execute(
        select(Issue)
        .where(and_(
            Issue.number == number,
            Issue.repository_id == repository_id
        ))
    )
    return result.scalar_one_or_none()

async def get_deleted_issue_by_number(session: AsyncSession, number: int, repository_id: int) -> Optional[DeletedIssue]:
    """Get deleted issue by its number."""
    result = await session.execute(
        select(DeletedIssue)
        .where(and_(
            DeletedIssue.number == number,
            DeletedIssue.repository_id == repository_id
        ))
    )
    return result.scalar_one_or_none()

async def get_repository_by_owner_and_name(session: AsyncSession, owner: str, name: str) -> Optional[Repository]:
    """Get repository by owner and name."""
    result = await session.execute(
        select(Repository)
        .where(and_(
            Repository.owner == owner,
            Repository.name == name
        ))
    )
    return result.scalar_one_or_none()

async def save_repository_languages(
    session: AsyncSession, 
    repository_id: int, 
    languages: Dict[str, int]
) -> List[RepositoryLanguage]:
    """Save repository languages to the database."""
    # Delete existing languages for this repository
    await session.execute(
        text("DELETE FROM repository_languages WHERE repository_id = :repo_id"),
        {"repo_id": repository_id}
    )
    
    # Create new language entries
    lang_objects = []
    for lang, bytes_count in languages.items():
        lang_obj = RepositoryLanguage(
            repository_id=repository_id,
            language=lang,
            bytes_count=bytes_count
        )
        session.add(lang_obj)
        lang_objects.append(lang_obj)
    
    await session.flush()
    return lang_objects

async def get_commits_by_ids(session: AsyncSession, commit_ids: List[int]) -> List[Commit]:
    """Get commits by their IDs."""
    if not commit_ids:
        return []
    result = await session.execute(
        select(Commit)
        .where(Commit.id.in_(commit_ids))
    )
    res = result.scalars().all()
    # sort the results by the order of commit_ids
    return sorted(res, key=lambda x: commit_ids.index(x.id))

async def save_pull_request_summary(
    session: AsyncSession,
    issue_id: int,
    summarization: str
) -> PullRequestSummary:
    """Save or update pull request summary."""
    result = await session.execute(
        select(PullRequestSummary).where(PullRequestSummary.issue_id == issue_id)
    )
    pr_summary = result.scalar_one_or_none()
    
    if pr_summary:
        pr_summary.summarization = summarization
        pr_summary.updated_at = datetime.now(timezone.utc)
    else:
        pr_summary = PullRequestSummary(
            issue_id=issue_id,
            summarization=summarization
        )
        session.add(pr_summary)
    
    await session.flush()
    return pr_summary

async def get_pull_request_summary(
    session: AsyncSession,
    issue_id: int
) -> Optional[PullRequestSummary]:
    """Get pull request summary by issue id."""
    result = await session.execute(
        select(PullRequestSummary).where(PullRequestSummary.issue_id == issue_id)
    )
    return result.scalar_one_or_none()

if __name__ == "__main__":
    import asyncio
    from sqlalchemy.orm import sessionmaker
    
    async def test_get_commit_summary():
        engine = create_async_engine(settings.database_url)
        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        
        # async with async_session() as session:
        #     result = await session.execute(
        #         text("delete FROM commit_summaries")
        #     )
        #     await session.commit()
        
        async with async_session() as session:
            result = await session.execute(
                text("SELECT summary FROM commit_summaries WHERE commit_id = 5")
            )
            summary = result.scalar_one_or_none()
            if summary:
                print(f"Commit Summary: {summary}")
            else:
                print("No summary found for commit_id 34")

    # Run the test
    # asyncio.run(test_get_commit_summary())


    async def get_readme_summary():
        engine = create_async_engine(settings.database_url)
        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async with async_session() as session:
            result = await session.execute(
                text("delete FROM readme_summaries")
            )
            await session.commit()

        # async with async_session() as session:
        #     result = await session.execute(
        #         text("SELECT summarization FROM readme_summaries WHERE repository_id = 2")
        #     )
        #     summary = result.scalar_one_or_none()
        #     if summary:
        #         print(f"Readme Summary: {summary}")
        #     else:
        #         print("No summary found for repository_id 1")

    # Run the test
    asyncio.run(get_readme_summary())