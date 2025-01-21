from typing import Optional, List, Tuple
from sqlalchemy.orm import Session
from backend.models.repository import (
    Commit, CommitDiff, Issue, RepositoryLanguage,
    ReadmeSummary
)
from .commit_summarizer import LLMSummarizer

def get_commit_data(
    db: Session, 
    commit_id: int
) -> tuple[Commit, List[CommitDiff], Optional[Issue], List[RepositoryLanguage], Optional[ReadmeSummary]]:
    """
    Retrieve commit data with related diffs, PR information, repository languages and readme summary
    """
    commit = db.query(Commit).filter(Commit.id == commit_id).first()
    if not commit:
        raise ValueError(f"Commit with id {commit_id} not found")
    
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
    
    return commit, diffs, pr, languages, readme_summary

def get_commits_without_summaries(db: Session) -> List[int]:
    """
    Find all commit IDs that don't have corresponding summaries
    """
    query = """
        SELECT c.id 
        FROM commits c 
        LEFT JOIN commit_summaries cs ON c.id = cs.commit_id 
        WHERE cs.id IS NULL
    """
    result = db.execute(query)
    return [row[0] for row in result]

def generate_commit_summary(commit_id: int, db: Session) -> str:
    """
    Generate a summary for a commit based on its data, diffs, PR, and repository context
    """
    commit, diffs, pr, languages, readme_summary = get_commit_data(db, commit_id)
    
    summarizer = LLMSummarizer()
    summary = summarizer.summarize_commit(
        diffs=diffs,
        languages=languages,
        readme_summary=readme_summary
    )
    
    return f"Summary of commit {commit.github_sha[:8]}: {summary}"

def save_commit_summary(db: Session, commit_id: int) -> None:
    """
    Generate and save commit summary to the database
    """
    from backend.models.repository import CommitSummary
    
    summary = generate_commit_summary(commit_id, db)
    
    # Create or update summary
    commit_summary = db.query(CommitSummary).filter(CommitSummary.commit_id == commit_id).first()
    if commit_summary:
        commit_summary.summary = summary
    else:
        commit_summary = CommitSummary(commit_id=commit_id, summary=summary)
        db.add(commit_summary)
    
    db.commit()
