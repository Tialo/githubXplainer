import asyncio
import traceback
import logging
from datetime import datetime
from backend.utils.logger import get_logger
from backend.services.summary_generator import save_commit_summary, get_commits_without_summaries, get_readme_without_summaries
from backend.services.readme_summarizer import ReadmeSummarizer
from backend.models.repository import ReadmeSummary, Repository
from backend.services.vector_store import VectorStore
from backend.db.database import SessionLocal

logger = get_logger(__name__)
logging.disable(logging.WARNING)
logging.getLogger('sqlalchemy').setLevel(logging.ERROR)


def log_info(msg):
    logger.info(f"[{datetime.now()}] {__name__} {msg}")


class SummaryService:
    def __init__(self):
        self.vector_store = VectorStore()
        self.is_running = False
        self.task = None
        self._shutdown_event = asyncio.Event()

    async def start(self):
        """Start the summary generation background task"""
        if not self.is_running:
            self._shutdown_event.clear()
            self.is_running = True
            self.task = asyncio.create_task(self._run_summary_loop())
            log_info("Summary generation service started")

    async def stop(self):
        """Stop the summary generation background task"""
        self.is_running = False
        self._shutdown_event.set()
        if self.task:
            try:
                await asyncio.wait_for(self.task, timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning("Summary service task did not stop gracefully, forcing cancellation")
                self.task.cancel()
                try:
                    await self.task
                except asyncio.CancelledError:
                    pass
            self.task = None
        logger.info("Summary generation service stopped")

    async def _run_summary_loop(self):
        """Main loop for summary generation"""
        while self.is_running and not self._shutdown_event.is_set():
            try:
                db = SessionLocal()
                try:
                    # Process commit summaries
                    commits = get_commits_without_summaries(db)
                    for commit_id in commits:
                        if self._shutdown_event.is_set():
                            break
                        summary, repo, commit = save_commit_summary(db, commit_id)
                        if summary:
                            self.vector_store.add_summary(
                                summary,
                                {
                                    "type": "commit",
                                    "commit_id": commit_id,
                                    "repo_id": repo.id,
                                    "date": commit.committed_date.isoformat()
                                }
                            )
                            log_info(f"Generated summary for commit {commit_id}")

                    # Process README summaries if we haven't been asked to shut down
                    if not self._shutdown_event.is_set():
                        for repo_id in get_readme_without_summaries(db):
                            if self._shutdown_event.is_set():
                                break
                            await self._process_readme_summary(db, repo_id)
                            log_info(f"Generated README summary for repository {repo_id}")

                finally:
                    db.close()

                # Sleep for a short duration, but be interruptible
                try:
                    await asyncio.wait_for(self._shutdown_event.wait(), timeout=1.0)
                except asyncio.TimeoutError:
                    pass

            except Exception as e:
                logger.error(f"Error in summary generation loop: {str(e)} {traceback.format_exc()}")
                # Make the error backoff interruptible
                try:
                    await asyncio.wait_for(self._shutdown_event.wait(), timeout=10.0)
                except asyncio.TimeoutError:
                    pass

    async def _process_readme_summary(self, db, repository_id):
        repository = db.query(Repository).filter(Repository.id == repository_id).first()
        if not repository or not repository.readme_content:
            return

        summarizer = ReadmeSummarizer()
        summary = summarizer.summarize(repository.readme_content)
        
        readme_summary = ReadmeSummary(
            repository_id=repository_id,
            summarization=summary
        )

        existing_summary = db.query(ReadmeSummary).filter(
            ReadmeSummary.repository_id == repository_id
        ).first()
        
        if existing_summary:
            existing_summary.summarization = summary
        else:
            db.add(readme_summary)
            
        db.commit()
        logger.info(f"Generated README summary for repository {repository_id}")

summary_service = SummaryService()
