from celery import shared_task
from backend.db.database import SessionLocal
from backend.services.summary_generator import save_commit_summary, get_commits_without_summaries
from backend.utils.logger import get_logger

logger = get_logger(__name__)

@shared_task(
    name="generate_commit_summary",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3
)
def generate_commit_summary_task(commit_id: int) -> None:
    """
    Celery task to generate and save commit summary.
    Includes automatic retry with exponential backoff on failure.
    """
    logger.info(f"Generating summary for commit {commit_id}")
    db = SessionLocal()
    try:
        save_commit_summary(db, commit_id)
        logger.info(f"Successfully generated summary for commit {commit_id}")
    except Exception as e:
        logger.error(f"Error generating summary for commit {commit_id}: {str(e)}")
        raise  # This will trigger the retry mechanism
    finally:
        db.close()

@shared_task(name="process_missing_summaries")
def process_missing_summaries_task() -> int:
    """
    Find commits without summaries and queue them for summary generation.
    Returns the number of commits queued.
    """
    db = SessionLocal()
    try:
        commit_ids = get_commits_without_summaries(db)
        for commit_id in commit_ids:
            generate_commit_summary_task.delay(commit_id)
        return len(commit_ids)
    except Exception as e:
        logger.error(f"Error processing missing summaries: {str(e)}")
        raise
    finally:
        db.close()
