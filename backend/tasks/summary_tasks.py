import sys
import six
if sys.version_info >= (3, 12, 0):
    sys.modules['kafka.vendor.six.moves'] = six.moves

from backend.kafka.kafka_service import KafkaInterface
from backend.db.database import SessionLocal
from backend.services.summary_generator import save_commit_summary, get_commits_without_summaries
from backend.services.readme_summarizer import ReadmeSummarizer
from backend.models.repository import ReadmeSummary, Repository
from backend.utils.logger import get_logger

logger = get_logger(__name__)
kafka = KafkaInterface()


def generate_readme_summary_task(repository_id: int):
    logger.info(f"Generating summary task for README {repository_id}")
    kafka.write_to_topic("readme", {"repository_id": repository_id})


def generate_commit_summary_task(commit_id: int) -> None:
    """
    RQ task to generate and save commit summary.
    Uses Redis lock to ensure only one summarization runs at a time.
    """
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


def schedule_missing_summaries():
    """
    Function to find commits without summaries and queue them.
    This will be scheduled via RQ-Scheduler.
    """
    db = SessionLocal()
    try:
        commit_ids = get_commits_without_summaries(db)
        logger.info(f"Found {len(commit_ids)} commits without summaries")
        for ci in commit_ids:
            kafka.write_to_topic("commit", {"commit_id": ci})
    except Exception as e:
        logger.error(f"Error processing missing summaries: {str(e)}")
        raise
    finally:
        db.close()


def do_readme_summary_task(repository_id: int):
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

if __name__ == '__main__':
    import time
    last_scheduled = time.time()
    logger.info("Starting summary tasks")
    
    # Initialize kafka service and consumer
    kafka = KafkaInterface()
    
    try:
        while True:
            if last_scheduled + 10 < time.time():
                schedule_missing_summaries()
                last_scheduled = time.time()
            for message in kafka.read_from_topic("commit"):
                logger.info(f"Received commit message: {message}")
                try:
                    generate_commit_summary_task(message.get("commit_id"))
                except Exception as e:
                    logger.error(f"Error processing commit message: {str(e)}")
                    logger.exception("as")
            for message in kafka.read_from_topic("readme"):
                logger.info(f"Received README message: {message}")
                try:
                    do_readme_summary_task(message.get("repository_id"))
                except Exception as e:
                    logger.error(f"Error processing README message: {str(e)}")
                    
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down summary tasks")
    finally:
        kafka.close()