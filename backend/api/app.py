from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from backend.services.repository_service import repository_service
from backend.config.settings import get_session
from backend.db.database import init_db

app = FastAPI(title="GitHub Xplainer")

@app.on_event("startup")
async def startup_event():
    """Initialize the database on app startup."""
    await init_db()

class RepositoryInit(BaseModel):
    owner: str
    repo: str

class RepositoryResponse(BaseModel):
    full_name: str
    commits_processed: int
    issues_processed: int
    prs_processed: int
    message: str

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
            full_name=repository.full_name,
            commits_processed=commits_count,
            issues_processed=issues_count,
            prs_processed=prs_count,
            message="Repository initialization completed successfully"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
