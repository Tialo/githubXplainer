from typing import Optional, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import text
from backend.models.repository import (
    Commit, CommitDiff, Issue, RepositoryLanguage,
    ReadmeSummary, Repository
)
from backend.utils.logger import get_logger
from backend.db.database import SessionLocal
from .commit_summarizer import LLMSummarizer


logger = get_logger(__name__)


class CommitNotFoundError(Exception):
    pass

def get_commit_data(
    db: Session, 
    commit_id: int
) -> tuple[Commit, List[CommitDiff], Optional[Issue], List[RepositoryLanguage], Optional[ReadmeSummary], str]:
    """
    Retrieve commit data with related diffs, PR information, repository languages and readme summary
    Returns tuple: (commit, diffs, pr, languages, readme_summary, repo_path)
    """
    commit = db.query(Commit)\
        .join(Repository)\
        .filter(Commit.id == commit_id)\
        .first()
    if not commit:
        raise CommitNotFoundError(f"Commit with id {commit_id} not found")
    
    # Get all diffs for the commit
    diffs = db.query(CommitDiff).filter(CommitDiff.commit_id == commit_id).all()
    
    # Get related PR if exists
    pr = None
    if commit.pull_request_number:
        pr = db.query(Issue).filter(
            Issue.repository_id == commit.repository_id,
            Issue.number == commit.pull_request_number,
            Issue.is_pull_request == True
        ).first()
    
    # Get repository languages
    languages = db.query(RepositoryLanguage).filter(
        RepositoryLanguage.repository_id == commit.repository_id
    ).all()
    
    # Get readme summary
    readme_summary = db.query(ReadmeSummary).filter(
        ReadmeSummary.repository_id == commit.repository_id
    ).first()
    
    # Get repository info
    repository = db.query(Repository).filter(Repository.id == commit.repository_id).first()
    repo_path = f"{repository.owner}/{repository.name}"
    
    return commit, diffs, pr, languages, readme_summary, repo_path

def get_commits_without_summaries(db: Session) -> List[int]:
    """
    Find all commit IDs that don't have corresponding summaries
    """
    query = text("""
        SELECT c.id 
        FROM commits c 
        LEFT JOIN commit_summaries cs ON c.id = cs.commit_id 
        WHERE cs.id IS NULL limit 5
    """)
    result = db.execute(query)
    return [row[0] for row in result]

def get_readme_without_summaries(db: Session) -> List[int]:
    """
    Find all repositories with READMEs that don't have corresponding summaries
    """
    query = text("""
        SELECT r.id 
        FROM repositories r 
        LEFT JOIN readme_summaries rs ON r.id = rs.repository_id 
        WHERE rs.id IS NULL
    """)
    result = db.execute(query)
    return [row[0] for row in result]

def generate_commit_summary(commit_id: int, db: Session) -> str:
    """
    Generate a summary for a commit based on its data, diffs, PR, and repository context
    """
    commit, diffs, pr, languages, readme_summary, repo_path = get_commit_data(db, commit_id)
    
    summarizer = LLMSummarizer()
    return summarizer.summarize_commit(
        diffs=diffs,
        languages=languages,
        readme_summary=readme_summary,
        repo_path=repo_path
    )

def save_commit_summary(db: Session, commit_id: int) -> None:
    """
    Generate and save commit summary to the database
    """
    from backend.models.repository import CommitSummary

    # if commit has summary then return
    commit_summary = db.query(CommitSummary).filter(CommitSummary.commit_id == commit_id).first()
    if commit_summary:
        return
    
    try:
        summary = generate_commit_summary(commit_id, db)
    except CommitNotFoundError:
        logger.error(f"Commit with id {commit_id} not found")
        return
    
    # Create or update summary
    commit_summary = db.query(CommitSummary).filter(CommitSummary.commit_id == commit_id).first()
    if commit_summary:
        commit_summary.summary = summary
    else:
        commit_summary = CommitSummary(commit_id=commit_id, summary=summary)
        db.add(commit_summary)
    
    db.commit()


if __name__ == '__main__':
    db = SessionLocal()
    print(get_commits_without_summaries(db))
