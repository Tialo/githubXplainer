import pytest
from elasticsearch import AsyncElasticsearch
from backend.services.elasticsearch.indexer import Indexer
from backend.models.repository import Commit
from datetime import datetime, timezone

@pytest.mark.asyncio
async def test_index_commit(elasticsearch_client: AsyncElasticsearch):
    indexer = Indexer(elasticsearch_client)
    
    # Create test commit
    commit = Commit(
        github_sha="test123",
        message="Test commit message",
        author_name="Test Author",
        authored_date=datetime.now(timezone.utc),
        repository_id=1
    )
    
    # Index the commit
    await indexer.index_commit(commit)
    
    # Verify indexed document
    result = await elasticsearch_client.get(
        index=indexer.index_manager.get_index_name('commits'),
        id=commit.github_sha
    )
    
    assert result['_source']['commit_hash'] == commit.github_sha
    assert result['_source']['message'] == commit.message
