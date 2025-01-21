from backend.config.huey_config import huey
from huey.api import TaskLock
from sqlalchemy.orm import Session
from backend.db.database import SessionLocal
from backend.services.summary_generator import save_commit_summary, get_commits_without_summaries
from backend.utils.logger import get_logger
from backend.models.repository import ReadmeSummary, Repository
from backend.services.readme_summarizer import ReadmeSummarizer
from datetime import timedelta

logger = get_logger(__name__)

@huey.task(retries=3, retry_delay=timedelta(minutes=1))
def generate_commit_summary_task(commit_id: int) -> None:
    """
    Huey task to generate and save commit summary.
    Uses locking to ensure only one summarization runs at a time.
    """
    with TaskLock('summarization_lock', timeout=3600):  # 1 hour timeout
        logger.info(f"Generating summary for commit {commit_id}")
        db = SessionLocal()
        try:
            save_commit_summary(db, commit_id)
            logger.info(f"Successfully generated summary for commit {commit_id}")
        except Exception as e:
            logger.error(f"Error generating summary for commit {commit_id}: {str(e)}")
            raise
        finally:
            db.close()

@huey.periodic_task(retry_delay=timedelta(minutes=10))
def process_missing_summaries_task() -> int:
    """
    Periodic task to find commits without summaries and queue them.
    Only queues next task when previous one is complete.
    """
    db = SessionLocal()
    try:
        commit_ids = get_commits_without_summaries(db)
        # Only queue one task at a time
        for commit_id in commit_ids:
            # Check if lock is available before queueing
            if not TaskLock.is_locked('summarization_lock'):
                generate_commit_summary_task(commit_id)
                # Only queue one task, then exit
                return 1
        return 0
    except Exception as e:
        logger.error(f"Error processing missing summaries: {str(e)}")
        raise
    finally:
        db.close()

@huey.task()
def generate_readme_summary_task(repository_id: int):
    with TaskLock('summarization_lock', timeout=3600):  # 1 hour timeout
        db = SessionLocal()
        try:
            repository = db.query(Repository).filter(Repository.id == repository_id).first()
            if not repository or not repository.readme_content:
                return
            
            summarizer = ReadmeSummarizer()
            summary = summarizer.summarize(repository.readme_content)
            
            readme_summary = ReadmeSummary(
                repository_id=repository_id,
                **summary
            )
            
            # Update or create summary
            existing_summary = db.query(ReadmeSummary).filter(
                ReadmeSummary.repository_id == repository_id
            ).first()
            
            if existing_summary:
                for key, value in summary.items():
                    setattr(existing_summary, key, value)
            else:
                db.add(readme_summary)
                
            db.commit()
        finally:
            db.close()
