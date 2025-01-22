import logging
from backend.db.database import SessionLocal
from backend.services.summary_generator import save_commit_summary, get_commits_without_summaries, get_readme_without_summaries
from backend.services.readme_summarizer import ReadmeSummarizer
from backend.models.repository import ReadmeSummary, Repository
from backend.utils.logger import get_logger
from datetime import datetime
from backend.services.vector_store import VectorStore

logger = get_logger(__name__)
logger.setLevel(logging.INFO)
logging.disable(logging.WARNING)
logging.getLogger('sqlalchemy').setLevel(logging.ERROR)

vector_store = VectorStore()

def log_info(text, *params):
    print(f"[{datetime.now()}] {text % params}")

def log_error(text, *params):
    print(f"[{datetime.now()}] ERROR: {text % params}")


def generate_commit_summary_task(commit_id: int) -> None:
    """
    RQ task to generate and save commit summary.
    Uses Redis lock to ensure only one summarization runs at a time.
    """
    log_info(f"Generating summary for commit {commit_id}")
    db = SessionLocal()
    try:
        summary = save_commit_summary(db, commit_id)
        if summary is not None:
            # Store summary embedding
            vector_store.add_summary(
                summary,
                {"type": "commit", "commit_id": commit_id}
            )
            log_info(f"Successfully generated summary and embedding for commit {commit_id}")
    except Exception as e:
        log_error(f"Error generating summary for commit {commit_id}: {str(e)}")
        raise
    finally:
        db.close()


def schedule_missing_summaries():
    """
    Function to find commits without summaries and queue them.
    """
    db = SessionLocal()
    try:
        commit_ids = get_commits_without_summaries(db)
        log_info(f"Found {len(commit_ids)} commits without summaries")
        return commit_ids
    except Exception as e:
        log_error(f"Error processing missing summaries: {str(e)}")
        raise
    finally:
        db.close()

def schedule_missing_readme_summaries():
    """
    Function to find repositories without readme summaries and queue them.
    """
    db = SessionLocal()
    try:
        repository_ids = get_readme_without_summaries(db)
        log_info(f"Found {len(repository_ids)} repositories without readme summaries")
        return repository_ids
    except Exception as e:
        log_error(f"Error processing missing readme summaries: {str(e)}")
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
        log_info(f"Summarizing README for repository {repository_id}")
        summary = summarizer.summarize(repository.readme_content)
        
        readme_summary = ReadmeSummary(
            repository_id=repository_id,
            summarization=summary
        )
        log_info("Saving summary for repository %d", repository_id)
        
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
    print("Starting summary tasks")

    
    while True:
        try:
            # Read messages from topics
            for commit_id in schedule_missing_summaries():
                log_info(f"Received commit message: {commit_id}")
                try:
                    generate_commit_summary_task(commit_id)
                except Exception as e:
                    log_error(f"Error processing commit message: {str(e)}")
                    
            for repository_id in schedule_missing_readme_summaries():
                log_info(f"Received README message: {repository_id}")
                try:
                    do_readme_summary_task(repository_id)
                except Exception as e:
                    log_error(f"Error processing README message: {str(e)}")
            
            time.sleep(1)
        except Exception as e:
            log_error(f"Error in main loop: {str(e)}")
            time.sleep(10)
            continue
