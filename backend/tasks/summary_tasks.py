import redis
from rq import Queue
from rq.decorators import job
from rq_scheduler import Scheduler
from datetime import timedelta, datetime

from backend.config.redis_config import redis_conn
from backend.db.database import SessionLocal
from backend.services.summary_generator import save_commit_summary, get_commits_without_summaries
from backend.services.readme_summarizer import ReadmeSummarizer
from backend.models.repository import ReadmeSummary, Repository
from backend.utils.logger import get_logger

logger = get_logger(__name__)

# Initialize RQ queue and scheduler
queue = Queue(connection=redis_conn)
scheduler = Scheduler(connection=redis_conn)

@job('default', connection=redis_conn, retry=3)
def generate_commit_summary_task(commit_id: int) -> None:
    """
    RQ task to generate and save commit summary.
    Uses Redis lock to ensure only one summarization runs at a time.
    """
    lock = redis_conn.lock('summarization_lock', timeout=3600)  # 1 hour timeout
    if not lock.acquire(blocking=False):
        logger.info("Another summarization task is running")
        return
    
    try:
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
    finally:
        lock.release()

def schedule_missing_summaries():
    """
    Function to find commits without summaries and queue them.
    This will be scheduled via RQ-Scheduler.
    """
    db = SessionLocal()
    try:
        commit_ids = get_commits_without_summaries(db)
        # Only queue one task if no summarization is running
        for commit_id in commit_ids:
            if not redis_conn.exists('summarization_lock'):
                queue.enqueue(generate_commit_summary_task, commit_id)
                return 1
        return 0
    except Exception as e:
        logger.error(f"Error processing missing summaries: {str(e)}")
        raise
    finally:
        db.close()

# Schedule the missing summaries task to run every 10 minutes
scheduler.schedule(
    scheduled_time=datetime.utcnow(),
    func=schedule_missing_summaries,
    interval=600  # 10 minutes in seconds
)

@job('default', connection=redis_conn)
def generate_readme_summary_task(repository_id: int):
    lock = redis_conn.lock('summarization_lock', timeout=3600)
    if not lock.acquire(blocking=False):
        logger.info("Another summarization task is running")
        return

    try:
        db = SessionLocal()
        try:
            repository = db.query(Repository).filter(Repository.id == repository_id).first()
            if not repository or not repository.readme_content:
                return
            
            summarizer = ReadmeSummarizer()
            summary = summarizer.summarize(repository.readme_content)
            
            readme_summary = ReadmeSummary(
                repository_id=repository_id,
                summarization=summary
            )
            
            # Update or create summary
            existing_summary = db.query(ReadmeSummary).filter(
                ReadmeSummary.repository_id == repository_id
            ).first()
            
            if existing_summary:
                setattr(existing_summary, 'summarization', summary)
            else:
                db.add(readme_summary)
                
            db.commit()
        finally:
            db.close()
    finally:
        lock.release()
