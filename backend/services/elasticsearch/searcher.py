import asyncio
from elasticsearch import AsyncElasticsearch
from elasticsearch.helpers import async_bulk
from backend.services.elasticsearch.index_manager import IndexManager
from typing import Dict, List, Any, Optional
from datetime import datetime
import logging
from backend.models.repository import CommitDiff, Issue, PullRequest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

logger = logging.getLogger(__name__)

class Searcher:
    def __init__(self, client: AsyncElasticsearch):
        self.client = client
        self.index_manager = IndexManager(client)

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
        size: int = 10
    ) -> List[Dict[str, Any]]:
        must_conditions = [
            {
                "multi_match": {
                    "query": query,
                    "fields": ["title^3", "body^2", "comments.content"]
                }
            },
            {"term": {"metadata.repository_id": repository_id}}
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
        base_branch: Optional[str] = None,
        from_date: Optional[datetime] = None,
        size: int = 10
    ) -> List[Dict[str, Any]]:
        must_conditions = [
            {
                "multi_match": {
                    "query": query,
                    "fields": ["title^3", "description^2", "reviews.comment"]
                }
            },
            {"term": {"metadata.repository_id": repository_id}}
        ]

        if state:
            must_conditions.append({"term": {"metadata.state": state}})
        if base_branch:
            must_conditions.append({"term": {"metadata.base_branch": base_branch}})
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
                index=self.index_manager.get_index_name('pull_requests'),
                body=body
            )
            return [hit["_source"] for hit in response["hits"]["hits"]]
        except Exception as e:
            logger.error(f"Error searching pull requests: {e}")
            raise

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
                self.search_issues(query, repository_id, from_date=from_date, size=size),
                self.search_pull_requests(query, repository_id, from_date=from_date, size=size)
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
                                    "max_query_terms": 12
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
            # First ensure indices exist
            await self.index_manager.ensure_indices()
            
            # Initialize commits
            async def commit_generator():
                query = select(CommitDiff)
                result = await db_session.execute(query)
                commits = result.scalars().all()
                
                for commit in commits:
                    yield {
                        "_index": self.index_manager.get_index_name('commits'),
                        "_source": {
                            "commit_hash": commit.commit_hash,
                            "message": commit.diff_content,
                            "metadata": {
                                "repository_id": commit.repository_id,
                                "file_path": commit.file_path,
                                "date": commit.created_at.isoformat()
                            }
                        }
                    }

            # Initialize issues
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
                                "labels": issue.labels
                            }
                        }
                    }

            # Initialize pull requests
            async def pr_generator():
                query = select(PullRequest)
                result = await db_session.execute(query)
                prs = result.scalars().all()
                
                for pr in prs:
                    yield {
                        "_index": self.index_manager.get_index_name('pull_requests'),
                        "_source": {
                            "title": pr.title,
                            "description": pr.body,  # Changed from pr.description to pr.body
                            "metadata": {
                                "repository_id": pr.repository_id,
                                "state": pr.state,
                                "base_branch": pr.base_branch,
                                "created_at": pr.created_at.isoformat()
                            }
                        }
                    }

            # Bulk index the data
            for generator in [commit_generator(), issue_generator(), pr_generator()]:
                await async_bulk(self.client, generator)
            
            logger.info("Successfully initialized Elasticsearch indices with PostgreSQL data")
            
        except Exception as e:
            logger.error(f"Failed to initialize Elasticsearch indices: {e}")
            raise
