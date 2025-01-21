from typing import Optional, List
from sqlalchemy.orm import Session
from backend.models.repository import Commit, CommitDiff, Issue

def get_commit_data(db: Session, commit_id: int) -> tuple[Commit, List[CommitDiff], Optional[Issue]]:
    """
    Retrieve commit data with related diffs and PR information
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
    
    return commit, diffs, pr

def generate_commit_summary(commit_id: int, db: Session) -> str:
    """
    Generate a summary for a commit based on its data, diffs, and related PR
    """
    commit, diffs, pr = get_commit_data(db, commit_id)
    
    # TODO: Implement actual summary generation logic
    # This is a placeholder that returns a basic summary
    return f"Summary of commit {commit.github_sha[:8]}: {commit.message}"

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
