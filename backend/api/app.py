import traceback
import logging
from fastapi import FastAPI, HTTPException, Depends, Body
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from backend.services.repository_service import repository_service
from backend.config.settings import get_session
from backend.db.database import init_db
from backend.services.elasticsearch.searcher import Searcher
from backend.config.elasticsearch import get_elasticsearch_client
from typing import Optional, List
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = FastAPI(title="GitHub Xplainer")

@app.on_event("startup")
async def startup_event():
    """Initialize the database on app startup."""
    await init_db()

class RepositoryInit(BaseModel):
    owner: str
    repo: str

class RepositoryResponse(BaseModel):
    owner: str
    name: str
    commits_processed: int
    issues_processed: int
    prs_processed: int
    message: str

class ElasticsearchInitResponse(BaseModel):
    status: str
    indices_initialized: int
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

class SearchResponse(BaseModel):
    total: int
    took: float
    results: List[SearchResult]

class SimilaritySearchResponse(BaseModel):
    total: int
    took: float
    similar_items: List[SearchResult]

@app.post("/repos/init", response_model=RepositoryResponse)
async def initialize_repository(
    repo_init: RepositoryInit,
    session: AsyncSession = Depends(get_session)
):
    try:
        repository, commits_count, issues_count, prs_count = await repository_service.initialize_repository(
            session,
            repo_init.owner,
            repo_init.repo
        )
        
        return RepositoryResponse(
            owner=repository.owner,
            name=repository.name,
            commits_processed=commits_count,
            issues_processed=issues_count,
            prs_processed=prs_count,
            message="Repository initialization completed successfully"
        )
    except Exception as e:
        error_detail = {
            "type": type(e).__name__,
            "message": str(e),
            "traceback": traceback.format_exc()
        }
        logger.error(f"Error processing repository: {error_detail}")
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
        searcher = Searcher(es_client)
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
        logger.error(f"Error initializing Elasticsearch: {error_detail}")
        raise HTTPException(
            status_code=500,
            detail=error_detail
        )

@app.post("/search/all", response_model=SearchResponse)
async def search_all_content(query: SearchQuery):
    """Search across commits, issues, and pull requests."""
    try:
        es_client = await get_elasticsearch_client()
        searcher = Searcher(es_client)
        results = await searcher.search_all(
            query.query,
            query.repository_id,
            query.from_date,
            query.size
        )
        return results
    except Exception as e:
        logger.error(f"Search error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/search/{content_type}", response_model=SearchResponse)
async def search_content(
    content_type: str,
    query: ContentSearchQuery
):
    """Search specific content type with filters."""
    try:
        es_client = await get_elasticsearch_client()
        searcher = Searcher(es_client)
        
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
        logger.error(f"Search error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/search/similar")
async def find_similar(query: SimilaritySearchQuery):
    """Find similar issues or pull requests based on text content."""
    raise HTTPException(status_code=501, detail="Not implemented")
    try:
        if query.content_type not in ['issues', 'pull_requests']:
            raise HTTPException(status_code=400, detail="Content type must be 'issues' or 'pull_requests'")
        
        logger.info(f"Searching for similar {query.content_type} based on: {query.text}")
        es_client = await get_elasticsearch_client()
        searcher = Searcher(es_client)
        results = await searcher.suggest_similar(
            query.text,
            query.content_type,
            query.repository_id,
            query.size
        )
        return results
    except Exception as e:
        logger.error(f"Similarity search error: {str(e)}")
        error_detail = {
            "type": type(e).__name__,
            "message": str(e),
            "traceback": traceback.format_exc()
        }
        logger.error(f"Error processing repository: {error_detail}")
        raise HTTPException(
            status_code=500,
            detail=error_detail
        )
