from typing import Optional, List, Tuple
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from backend.models.repository import (
    Commit, CommitDiff, Issue, RepositoryLanguage,
    ReadmeSummary, Repository, CommitSummary, IssueComment,
    PullRequestSummary
)
from backend.utils.logger import get_logger
from backend.config.settings import async_session
from .commit_summarizer import LLMSummarizer
from .pr_summarizer import PullRequestDiscussionSummarizer

logger = get_logger(__name__)

class CommitNotFoundError(Exception):
    pass

class PullRequestNotFoundError(Exception):
    pass

async def get_commit_data(
    db: AsyncSession, 
    commit_id: int
) -> tuple[Commit, List[CommitDiff], Optional[Issue], List[RepositoryLanguage], Optional[ReadmeSummary], Repository, Optional[PullRequestSummary]]:
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
    pr_summary = None
    if commit.pull_request_number:
        result = await db.execute(
            select(Issue).filter(
                Issue.repository_id == commit.repository_id,
                Issue.number == commit.pull_request_number,
                Issue.is_pull_request == True
            )
        )
        pr = result.scalar_one_or_none()
        
        if pr:
            result = await db.execute(
                select(PullRequestSummary).filter(
                    PullRequestSummary.issue_id == pr.id
                )
            )
            pr_summary = result.scalar_one_or_none()
    
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
    
    return commit, diffs, pr, languages, readme_summary, repository, pr_summary

async def get_pr_data(
    db: AsyncSession,
    pr_id: int
) -> tuple[Issue, List[IssueComment], List[RepositoryLanguage], Optional[ReadmeSummary], Repository]:
    """
    Retrieve pull request data with related comments, repository languages and readme summary
    """
    result = await db.execute(
        select(Issue)
        .join(Repository)
        .filter(Issue.id == pr_id, Issue.is_pull_request == True)
    )
    pr = result.scalar_one_or_none()
    if not pr:
        raise PullRequestNotFoundError(f"Pull request with id {pr_id} not found")
    
    # Get all comments for the PR
    result = await db.execute(
        select(IssueComment).filter(IssueComment.issue_id == pr_id)
    )
    comments = result.scalars().all()
    
    # Get repository languages
    result = await db.execute(
        select(RepositoryLanguage).filter(
            RepositoryLanguage.repository_id == pr.repository_id
        )
    )
    languages = result.scalars().all()
    
    # Get readme summary
    result = await db.execute(
        select(ReadmeSummary).filter(
            ReadmeSummary.repository_id == pr.repository_id
        )
    )
    readme_summary = result.scalar_one_or_none()
    
    # Get repository info
    result = await db.execute(
        select(Repository).filter(Repository.id == pr.repository_id)
    )
    repository = result.scalar_one()
    
    return pr, comments, languages, readme_summary, repository

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

async def get_prs_without_summaries(db: AsyncSession) -> List[int]:
    """Find all pull request IDs that are linked to commits but don't have corresponding summaries"""
    result = await db.execute(
        text("""
            SELECT DISTINCT i.id 
            FROM issues i
            INNER JOIN commits c ON i.repository_id = c.repository_id 
                AND i.number = c.pull_request_number
            LEFT JOIN pull_request_summaries prs ON i.id = prs.issue_id
            WHERE i.is_pull_request = true 
            AND prs.id IS NULL
            LIMIT 5
        """)
    )
    return [row[0] for row in result.all()]

async def generate_commit_summary(commit_id: int, db: AsyncSession) -> Tuple[str, Repository]:
    """Generate a summary for a commit based on its data"""
    commit, diffs, pr, languages, readme_summary, repository, pr_summary = await get_commit_data(db, commit_id)
    
    summarizer = LLMSummarizer()
    return await summarizer.summarize_commit(
        diffs=diffs,
        languages=languages,
        readme_summary=readme_summary,
        repository=repository,
        commit=commit,
        pr=pr,
        pr_summary=pr_summary,
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

async def generate_pr_summary(pr_id: int, db: AsyncSession) -> Tuple[str, Repository, Issue]:
    """Generate a summary for a pull request based on its data"""
    pr, comments, languages, readme_summary, repository = await get_pr_data(db, pr_id)
    
    summarizer = PullRequestDiscussionSummarizer()
    summary = await summarizer.summarize_pull_request_discussion(
        issue=pr,
        comments=comments,
        languages=languages,
        readme_summary=readme_summary,
        repository=repository
    )
    return summary, repository, pr

async def save_pr_summary(db: AsyncSession, pr_id: int) -> Optional[Tuple[str, Repository, Issue]]:
    """Generate and save pull request summary to the database"""
    # Check for existing summary
    result = await db.execute(
        select(PullRequestSummary).filter(PullRequestSummary.issue_id == pr_id)
    )
    if result.scalar_one_or_none():
        return None
    
    try:
        summary, repo, pr = await generate_pr_summary(pr_id, db)
    except PullRequestNotFoundError:
        logger.error(f"Pull request with id {pr_id} not found")
        return None
    
    pr_summary = PullRequestSummary(
        issue_id=pr_id,
        summarization=summary
    )
    db.add(pr_summary)
    await db.commit()
    return summary, repo, pr

if __name__ == '__main__':
    import asyncio
    
    async def main():
        async with async_session() as session:
            result = await get_commits_without_summaries(session)
            print(result)
    
    asyncio.run(main())
