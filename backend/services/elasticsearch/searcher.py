import asyncio
from elasticsearch import AsyncElasticsearch
from elasticsearch.helpers import async_bulk
from backend.services.elasticsearch.index_manager import IndexManager
from typing import Dict, List, Any, Optional
from datetime import datetime
import logging
from backend.models.repository import CommitDiff, Issue, Commit
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

logger = logging.getLogger(__name__)

class Searcher:
    def __init__(self, client: AsyncElasticsearch):
        self.client = client
        self.index_manager = IndexManager(client)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.close()

    async def search_commits(
        self, 
        query: str, 
        repository_id: int, 
        from_date: Optional[datetime] = None,
        size: int = 10,
        sort_by: str = "date"
    ) -> List[Dict[str, Any]]:
        must_conditions = [
            {"match": {"message": query}},
            {"term": {"metadata.repository_id": repository_id}}
        ]
        
        if from_date:
            must_conditions.append({
                "range": {
                    "metadata.date": {
                        "gte": from_date.isoformat()
                    }
                }
            })

        body = {
            "query": {
                "bool": {
                    "must": must_conditions
                }
            },
            "size": size
        }

        response = await self.client.search(
            index=self.index_manager.get_index_name('commits'),
            body=body
        )
        
        return [hit["_source"] for hit in response["hits"]["hits"]]

    async def search_issues(
        self,
        query: str,
        repository_id: int,
        state: Optional[str] = None,
        labels: Optional[List[str]] = None,
        from_date: Optional[datetime] = None,
        size: int = 10,
        include_prs: bool = False
    ) -> List[Dict[str, Any]]:
        must_conditions = [
            {
                "multi_match": {
                    "query": query,
                    "fields": ["title^3", "body^2", "comments.content"]
                }
            },
            {"term": {"metadata.repository_id": repository_id}},
            {"term": {"metadata.is_pull_request": include_prs}}
        ]

        if state:
            must_conditions.append({"term": {"metadata.state": state}})
        if labels:
            must_conditions.append({"terms": {"metadata.labels": labels}})
        if from_date:
            must_conditions.append({
                "range": {
                    "metadata.created_at": {"gte": from_date.isoformat()}
                }
            })

        body = {
            "query": {"bool": {"must": must_conditions}},
            "size": size,
            "sort": [{"metadata.created_at": "desc"}]
        }

        try:
            response = await self.client.search(
                index=self.index_manager.get_index_name('issues'),
                body=body
            )
            return [hit["_source"] for hit in response["hits"]["hits"]]
        except Exception as e:
            logger.error(f"Error searching issues: {e}")
            raise

    async def search_pull_requests(
        self,
        query: str,
        repository_id: int,
        state: Optional[str] = None,
        from_date: Optional[datetime] = None,
        size: int = 10
    ) -> List[Dict[str, Any]]:
        # Reuse issues search with PR filter
        return await self.search_issues(
            query=query,
            repository_id=repository_id,
            state=state,
            from_date=from_date,
            size=size,
            include_prs=True  # Force PR-only results
        )

    async def search_all(
        self,
        query: str,
        repository_id: int,
        from_date: Optional[datetime] = None,
        size: int = 10
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Search across all indices and return combined results."""
        try:
            results = await asyncio.gather(
                self.search_commits(query, repository_id, from_date, size),
                self.search_issues(query, repository_id, from_date=from_date, size=size, include_prs=False),
                self.search_issues(query, repository_id, from_date=from_date, size=size, include_prs=True)  # Get PRs
            )
            
            return {
                "commits": results[0],
                "issues": results[1],
                "pull_requests": results[2]
            }
        except Exception as e:
            logger.error(f"Error in combined search: {e}")
            raise

    async def suggest_similar(
        self,
        text: str,
        index: str,
        repository_id: int,
        size: int = 5
    ) -> List[Dict[str, Any]]:
        """Find similar items using more-like-this query."""
        try:
            body = {
                "query": {
                    "bool": {
                        "must": [
                            {
                                "more_like_this": {
                                    "fields": ["title", "body", "description", "message"],
                                    "like": text,
                                    "min_term_freq": 1,
                                    "min_doc_freq": 1,
                                }
                            },
                            {"term": {"metadata.repository_id": repository_id}}
                        ]
                    }
                },
                "size": size
            }

            response = await self.client.search(
                index=self.index_manager.get_index_name(index),
                body=body
            )
            return [hit["_source"] for hit in response["hits"]["hits"]]
        except Exception as e:
            logger.error(f"Error finding similar items: {e}")
            raise

    async def initialize_elasticsearch(self, db_session: AsyncSession) -> None:
        """Initialize Elasticsearch indices with data from PostgreSQL."""
        try:
            await self.index_manager.ensure_indices()
            
            # Initialize commits
            async def commit_generator():
                query = select(Commit)
                result = await db_session.execute(query)
                commits = result.scalars().all()
                
                for commit in commits:
                    yield {
                        "_index": self.index_manager.get_index_name('commits'),
                        "_source": {
                            "commit_hash": commit.github_sha,
                            "message": commit.message,
                            "metadata": {
                                "repository_id": commit.repository_id,
                                "date": commit.committed_date.isoformat()
                            }
                        }
                    }

            async def commit_diff_generator():
                query = select(CommitDiff).join(Commit)
                result = await db_session.execute(query)
                commit_diffs = result.scalars().all()
                
                for diff in commit_diffs:
                    yield {
                        "_index": self.index_manager.get_index_name('commits'),
                        "_source": {
                            "commit_hash": diff.commit.github_sha,
                            "message": diff.diff_content,
                            "metadata": {
                                "repository_id": diff.commit.repository_id,
                                "file_path": diff.file_path,
                                "date": diff.commit.committed_date.isoformat()
                            }
                        }
                    }

            # Initialize issues and PRs together
            async def issue_generator():
                query = select(Issue)
                result = await db_session.execute(query)
                issues = result.scalars().all()
                
                for issue in issues:
                    yield {
                        "_index": self.index_manager.get_index_name('issues'),
                        "_source": {
                            "title": issue.title,
                            "body": issue.body,
                            "metadata": {
                                "repository_id": issue.repository_id,
                                "state": issue.state,
                                "created_at": issue.created_at.isoformat(),
                                "labels": issue.labels,
                                "is_pull_request": issue.is_pull_request,
                            }
                        }
                    }

            # Bulk index the data
            for generator in [commit_generator(), commit_diff_generator(), issue_generator()]:
                await async_bulk(self.client, generator)
            
            logger.info("Successfully initialized Elasticsearch indices with PostgreSQL data")
            
        except Exception as e:
            logger.error(f"Failed to initialize Elasticsearch indices: {e}")
            raise

    async def clear_all_indices(self) -> Dict[str, Any]:
        """Clear all Elasticsearch indices."""
        try:
            indices = ['commits', 'issues']
            results = {}
            
            for index in indices:
                index_name = self.index_manager.get_index_name(index)
                if await self.client.indices.exists(index=index_name):
                    response = await self.client.delete_by_query(
                        index=index_name,
                        body={"query": {"match_all": {}}}
                    )
                    results[index] = {
                        "deleted": response.get("deleted", 0),
                        "total": response.get("total", 0)
                    }
            
            return results
        except Exception as e:
            logger.error(f"Failed to clear indices: {e}")
            raise
