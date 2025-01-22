import asyncio
import traceback
import logging
import signal
from fastapi import FastAPI, HTTPException, Depends, Body
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from backend.services.repository_service import repository_service
from backend.config.settings import get_session, settings, async_session  # Add this import
from backend.db.database import init_db
from backend.services.elasticsearch.searcher import Searcher
from backend.config.elasticsearch import get_elasticsearch_client
from typing import Optional, List
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from redis import Redis
from backend.utils.logger import get_logger
from backend.services.vector_store import VectorStore
from backend.services.summary_service import summary_service

logger = get_logger(__name__)
logger.setLevel(logging.DEBUG)

def log_info(text, *params):
    print(f"[{datetime.now()}] {text % params}")

def log_error(text, *params):
    print(f"[{datetime.now()}] ERROR: {text % params}")

logging.getLogger('sqlalchemy').setLevel(logging.ERROR)

app = FastAPI(title="GitHub Xplainer")

# Add these variables after the app initialization
scheduler = AsyncIOScheduler()
shutdown_event = asyncio.Event()

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    logger.info(f"Received signal {signum}")
    asyncio.create_task(shutdown())

async def shutdown():
    """Coordinate graceful shutdown of all services"""
    logger.info("Initiating graceful shutdown...")
    shutdown_event.set()
    
    # Stop the scheduler
    if settings.use_scheduler and scheduler.running:
        scheduler.shutdown(wait=True)
    
    # Stop summary generation service
    await summary_service.stop()
    
    logger.info("Shutdown complete")

# Replace the direct Redis client initialization with a function
def get_redis_client():
    return Redis(host='localhost', port=6379, db=0)

LOCK_KEY = "repository_update_lock"
LOCK_TIMEOUT = 300  # 5 minutes max lock time

async def periodic_repository_update():
    """Periodically update repository data with Redis lock."""
    redis_client = get_redis_client()
    # Try to acquire lock
    lock_acquired = redis_client.set(
        LOCK_KEY, 
        'locked', 
        ex=LOCK_TIMEOUT,
        nx=True
    )
    
    if not lock_acquired:
        log_info("Another update task is still running, skipping this run")
        return

    log_info("Starting periodic repository update")
    try:
        async with async_session() as session:
            async with session.begin():  # This creates a single transaction for all operations
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
                        log_error(f"Error updating repository {repo.owner}/{repo.name}: {str(e)}")
                        # Don't continue, rollback the entire transaction
                        raise
    except Exception as e:
        log_error(f"Error in periodic update: {str(e)}")
    finally:
        # Release lock even if there was an error
        redis_client.delete(LOCK_KEY)

@app.on_event("startup")
async def startup_event():
    """Initialize the database and services on app startup."""
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    await init_db()
    
    # Start summary generation service
    await summary_service.start()
    
    if settings.use_scheduler:
        # Run every 2 minutes
        scheduler.add_job(
            periodic_repository_update,
            trigger=IntervalTrigger(seconds=12),
            id='repository_updater',
            name='Repository periodic update',
            replace_existing=True,
            # max_instances=1  # Extra safety: ensure only one instance runs
        )
        scheduler.start()

@app.on_event("shutdown")
async def shutdown_event():
    """Shut down services when the app stops."""
    if settings.use_scheduler and scheduler.running:
        scheduler.shutdown(wait=False)
    
    # Stop summary generation service
    await summary_service.stop()

class RepositoryInit(BaseModel):
    owner: str
    repo: str

class RepositoryResponse(BaseModel):
    owner: str
    name: str
    commits_processed: int
    issues_processed: int
    message: str

class ElasticsearchInitResponse(BaseModel):
    status: str
    indices_initialized: int
    message: str

class ElasticsearchClearResponse(BaseModel):
    status: str
    indices_cleared: dict
    message: str

class SearchQuery(BaseModel):
    repository_id: int
    query: str
    from_date: Optional[datetime] = None
    size: int = 10

class ContentSearchQuery(SearchQuery):
    state: Optional[str] = None
    labels: Optional[List[str]] = None
    base_branch: Optional[str] = None

class SimilaritySearchQuery(BaseModel):
    repository_id: int
    text: str
    content_type: str
    size: Optional[int] = 5  # make size optional with default value

class SearchResult(BaseModel):
    id: int
    type: str
    title: Optional[str] = None
    content: str
    created_at: datetime
    score: float

class SimilaritySearchResponse(BaseModel):
    total: int
    took: float
    similar_items: List[SearchResult]

class RepositoryDelete(BaseModel):
    owner: str
    repo: str

class FAISSSimilarityQuery(BaseModel):
    query: str
    k: Optional[int] = 5

class FAISSSimilarityResult(BaseModel):
    text: str
    metadata: dict
    score: float
    search_time: float
    load_time: float

@app.get("/alive")
async def alive():
    return {"status": "alive"}

@app.post("/repos/init", response_model=RepositoryResponse)
async def initialize_repository(
    repo_init: RepositoryInit,
    session: AsyncSession = Depends(get_session)
):
    try:
        async with session.begin():  # Add transaction management
            repository, commits_count, issues_count = await repository_service.update_repository(
                session,
                repo_init.owner,
                repo_init.repo
            )
        
        return RepositoryResponse(
            owner=repository.owner,
            name=repository.name,
            commits_processed=commits_count,
            issues_processed=issues_count,
            message="Repository initialization completed successfully"
        )
    except Exception as e:
        error_detail = {
            "type": type(e).__name__,
            "message": str(e),
            "traceback": traceback.format_exc()
        }
        log_error(f"Error processing repository: {error_detail}")
        raise HTTPException(
            status_code=500,
            detail=error_detail
        )

@app.delete("/repos/delete", response_model=RepositoryResponse)
async def delete_repository(
    repo_delete: RepositoryDelete,
    session: AsyncSession = Depends(get_session)
):
    """Delete a repository and its associated data from both PostgreSQL."""
    try:
        # Delete from PostgreSQL
        repository = await repository_service.delete_repository(
            session,
            repo_delete.owner,
            repo_delete.repo
        )
        
        return RepositoryResponse(
            owner=repository.owner,
            name=repository.name,
            commits_processed=0,
            issues_processed=0,
            message="Repository successfully deleted"
        )
    except Exception as e:
        error_detail = {
            "type": type(e).__name__,
            "message": str(e),
            "traceback": traceback.format_exc()
        }
        log_error(f"Error deleting repository: {error_detail}")
        raise HTTPException(
            status_code=500,
            detail=error_detail
        )

@app.post("/elasticsearch/init", response_model=ElasticsearchInitResponse)
async def initialize_elasticsearch(
    session: AsyncSession = Depends(get_session)
):
    """Initialize Elasticsearch indices with data from PostgreSQL."""
    try:
        es_client = await get_elasticsearch_client()
        async with Searcher(es_client) as searcher:
            await searcher.initialize_elasticsearch(session)
            
            return ElasticsearchInitResponse(
                status="success",
                indices_initialized=3,  # commits, issues, pull_requests
                message="Successfully initialized Elasticsearch indices with PostgreSQL data"
            )
    except Exception as e:
        error_detail = {
            "type": type(e).__name__,
            "message": str(e),
            "traceback": traceback.format_exc()
        }
        log_error(f"Error initializing Elasticsearch: {error_detail}")
        raise HTTPException(
            status_code=500,
            detail=error_detail
        )

@app.post("/elasticsearch/clear", response_model=ElasticsearchClearResponse)
async def clear_elasticsearch():
    """Clear all data from Elasticsearch indices."""
    try:
        es_client = await get_elasticsearch_client()
        async with Searcher(es_client) as searcher:
            results = await searcher.clear_all_indices()
            
            return ElasticsearchClearResponse(
                status="success",
                indices_cleared=results,
                message="Successfully cleared all Elasticsearch indices"
            )
    except Exception as e:
        error_detail = {
            "type": type(e).__name__,
            "message": str(e),
            "traceback": traceback.format_exc()
        }
        log_error(f"Error clearing Elasticsearch indices: {error_detail}")
        raise HTTPException(
            status_code=500,
            detail=error_detail
        )

@app.post("/search/all")
async def search_all_content(query: SearchQuery):
    """Search across commits, issues, and pull requests."""
    try:
        es_client = await get_elasticsearch_client()
        async with Searcher(es_client) as searcher:
            results = await searcher.search_all(
                query.query,
                query.repository_id,
                query.from_date,
                query.size
            )
            return results
    except Exception as e:
        log_error(f"Search error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/search/type/{content_type}")
async def search_content(
    content_type: str,
    query: ContentSearchQuery
):
    """Search specific content type with filters."""
    try:
        es_client = await get_elasticsearch_client()
        async with Searcher(es_client) as searcher:
            if content_type == "commits":
                results = await searcher.search_commits(
                    query.query, 
                    query.repository_id,
                    query.from_date,
                    query.size
                )
            elif content_type == "issues":
                results = await searcher.search_issues(
                    query.query,
                    query.repository_id,
                    query.state,
                    query.labels,
                    query.from_date,
                    query.size
                )
            elif content_type == "pull_requests":
                results = await searcher.search_pull_requests(
                    query.query,
                    query.repository_id,
                    query.state,
                    query.base_branch,
                    query.from_date,
                    query.size
                )
            else:
                raise HTTPException(status_code=400, detail="Invalid content type")
            
            return results
    except Exception as e:
        log_error(f"Search error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/search/similar")
async def find_similar(query: SimilaritySearchQuery):
    """Find similar issues or pull requests based on text content."""
    try:
        if query.content_type not in ['issues', 'pull_requests']:
            raise HTTPException(status_code=400, detail="Content type must be 'issues' or 'pull_requests'")
        
        log_info(f"Searching for similar {query.content_type} based on: {query.text}")
        es_client = await get_elasticsearch_client()
        async with Searcher(es_client) as searcher:
            results = await searcher.suggest_similar(
                query.text,
                query.content_type,
                query.repository_id,
                query.size
            )
            return results
    except Exception as e:
        log_error(f"Similarity search error: {str(e)}")
        error_detail = {
            "type": type(e).__name__,
            "message": str(e),
            "traceback": traceback.format_exc()
        }
        log_error(f"Error processing repository: {error_detail}")
        raise HTTPException(
            status_code=500,
            detail=error_detail
        )

@app.post("/search/faiss", response_model=List[FAISSSimilarityResult])
async def search_faiss_similar(query: FAISSSimilarityQuery):
    """Find similar items using FAISS vector similarity."""
    try:
        import time
        start = time.time()
        vector_store = VectorStore()
        loaded_in = time.time() - start
        start = time.time()
        results = vector_store.search_similar(query.query, k=query.k)
        search_time = time.time() - start
        
        return [
            FAISSSimilarityResult(
                text="",
                metadata=doc.metadata,
                score=0.0,
                search_time=search_time,
                load_time=loaded_in
            ) 
            for doc in results
        ]
    except Exception as e:
        log_error(f"FAISS search error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

