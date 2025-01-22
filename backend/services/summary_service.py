import traceback
import logging
from datetime import datetime
from backend.utils.logger import get_logger
from backend.services.summary_generator import save_commit_summary, get_commits_without_summaries, get_readme_without_summaries
from backend.services.readme_summarizer import ReadmeSummarizer
from backend.models.repository import ReadmeSummary, Repository
from backend.services.vector_store import VectorStore
from backend.db.database import SessionLocal
from backend.config.settings import async_session
from backend.services.repository_service import repository_service

logger = get_logger(__name__)
logging.disable(logging.WARNING)
logging.getLogger('sqlalchemy').setLevel(logging.ERROR)


def log_info(msg):
    logger.info(f"[{datetime.now()}] {__name__} {msg}")


class SummaryService:
    def __init__(self):
        self.vector_store = VectorStore()
        self.is_running = False

    async def process_all_summaries(self):
        """Process both commits and README summaries in one go"""
        try:
            await self.process_commits()
            await self.process_readmes()
            await self.periodic_repository_update()
            log_info("Completed processing all summaries")
        except Exception as e:
            logger.error(f"Error in unified summary processing: {str(e)} {traceback.format_exc()}")

    async def process_commits(self):
        """Process pending commit summaries"""
        try:
            # Get commit IDs that need processing
            with SessionLocal() as db:
                commits = get_commits_without_summaries(db)

            # Process each commit with its own database session
            for commit_id in commits:
                with SessionLocal() as db:
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
        except Exception as e:
            logger.error(f"Error processing commits: {str(e)} {traceback.format_exc()}")

    async def process_readmes(self):
        """Process pending README summaries"""
        try:
            # Get repositories that need README processing
            with SessionLocal() as db:
                repo_ids = get_readme_without_summaries(db)

            # Process each README with its own database session
            for repo_id in repo_ids:
                with SessionLocal() as db:
                    await self._process_readme_summary(db, repo_id)
                    log_info(f"Generated README summary for repository {repo_id}")
        except Exception as e:
            logger.error(f"Error processing READMEs: {str(e)} {traceback.format_exc()}")

    async def _process_readme_summary(self, db, repository_id):
        """Process a single README summary"""
        repository = db.query(Repository).filter(Repository.id == repository_id).first()
        if not repository or not repository.readme_content:
            return

        summarizer = ReadmeSummarizer()
        summary = summarizer.summarize(repository.readme_content)
        
        # Query and update in same session
        existing_summary = db.query(ReadmeSummary).filter(
            ReadmeSummary.repository_id == repository_id
        ).first()
        
        if existing_summary:
            existing_summary.summarization = summary
        else:
            readme_summary = ReadmeSummary(
                repository_id=repository_id,
                summarization=summary
            )
            db.add(readme_summary)
            
        db.commit()
        log_info(f"Generated README summary for repository {repository_id}")

    async def periodic_repository_update(self):
        async with async_session() as session:
            async with session.begin():
                repos = await repository_service.get_all_initialized_repositories(session)
                log_info(f"Found {len(repos)} repositories to update")
                for repo in repos:
                    try:
                        _, commits_count, issues_count = await repository_service.update_repository(
                            session,
                            repo.owner,
                            repo.name
                        )
                        log_info(f"Successfully updated repository {repo.owner}/{repo.name}")
                        log_info(f"Commits processed: {commits_count}, Issues processed: {issues_count}")
                    except Exception as e:
                        log_info(f"Error updating repository {repo.owner}/{repo.name}: {str(e)}, {traceback.format_exc()}")
                        raise

summary_service = SummaryService()
