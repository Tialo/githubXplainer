from typing import Optional, List, Tuple
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from backend.models.repository import (
    Commit, CommitDiff, Issue, RepositoryLanguage,
    ReadmeSummary, Repository, CommitSummary
)
from backend.utils.logger import get_logger
from backend.config.settings import async_session
from .commit_summarizer import LLMSummarizer

logger = get_logger(__name__)

class CommitNotFoundError(Exception):
    pass

async def get_commit_data(
    db: AsyncSession, 
    commit_id: int
) -> tuple[Commit, List[CommitDiff], Optional[Issue], List[RepositoryLanguage], Optional[ReadmeSummary], Repository]:
    """
    Retrieve commit data with related diffs, PR information, repository languages and readme summary
    """
    result = await db.execute(
        select(Commit)
        .join(Repository)
        .filter(Commit.id == commit_id)
    )
    commit = result.scalar_one_or_none()
    if not commit:
        raise CommitNotFoundError(f"Commit with id {commit_id} not found")
    
    # Get all diffs for the commit
    result = await db.execute(
        select(CommitDiff).filter(CommitDiff.commit_id == commit_id)
    )
    diffs = result.scalars().all()
    
    # Get related PR if exists
    pr = None
    if commit.pull_request_number:
        result = await db.execute(
            select(Issue).filter(
                Issue.repository_id == commit.repository_id,
                Issue.number == commit.pull_request_number,
                Issue.is_pull_request == True
            )
        )
        pr = result.scalar_one_or_none()
    
    # Get repository languages
    result = await db.execute(
        select(RepositoryLanguage).filter(
            RepositoryLanguage.repository_id == commit.repository_id
        )
    )
    languages = result.scalars().all()
    
    # Get readme summary
    result = await db.execute(
        select(ReadmeSummary).filter(
            ReadmeSummary.repository_id == commit.repository_id
        )
    )
    readme_summary = result.scalar_one()
    
    # Get repository info
    result = await db.execute(
        select(Repository).filter(Repository.id == commit.repository_id)
    )
    repository = result.scalar_one_or_none()
    
    return commit, diffs, pr, languages, readme_summary, repository

async def get_commits_without_summaries(db: AsyncSession) -> List[int]:
    """Find all commit IDs that don't have corresponding summaries"""
    result = await db.execute(
        text("SELECT c.id FROM commits c LEFT JOIN commit_summaries cs ON c.id = cs.commit_id WHERE cs.id IS NULL limit 5")
    )
    return [row[0] for row in result.all()]

async def get_readme_without_summaries(db: AsyncSession) -> List[int]:
    """Find all repositories with READMEs that don't have corresponding summaries"""
    result = await db.execute(
        text("SELECT r.id FROM repositories r LEFT JOIN readme_summaries rs ON r.id = rs.repository_id WHERE rs.id IS NULL")
    )
    return [row[0] for row in result.all()]

async def generate_commit_summary(commit_id: int, db: AsyncSession) -> Tuple[str, Repository]:
    """Generate a summary for a commit based on its data"""
    commit, diffs, pr, languages, readme_summary, repository = await get_commit_data(db, commit_id)
    
    summarizer = LLMSummarizer()
    return await summarizer.summarize_commit(
        diffs=diffs,
        languages=languages,
        readme_summary=readme_summary,
        repository=repository,
        commit=commit,
    ), repository, commit

async def save_commit_summary(db: AsyncSession, commit_id: int) -> None:
    """Generate and save commit summary to the database"""
    # Check for existing summary
    result = await db.execute(
        select(CommitSummary).filter(CommitSummary.commit_id == commit_id)
    )
    if result.scalar_one_or_none():
        return
    
    try:
        summary, repo, commit = await generate_commit_summary(commit_id, db)
    except CommitNotFoundError:
        logger.error(f"Commit with id {commit_id} not found")
        return
    
    commit_summary = CommitSummary(commit_id=commit_id, summary=summary)
    db.add(commit_summary)
    await db.commit()
    return summary, repo, commit

if __name__ == '__main__':
    import asyncio
    
    async def main():
        async with async_session() as session:
            result = await get_commits_without_summaries(session)
            print(result)
    
    asyncio.run(main())
