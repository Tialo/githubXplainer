from elasticsearch import AsyncElasticsearch
from elasticsearch.helpers import async_bulk
from backend.services.elasticsearch.index_manager import IndexManager
from backend.models.repository import Commit, Issue, PullRequest, IssueComment, PullRequestComment
from typing import List, Dict, Any, Tuple
import asyncio

class Indexer:
    def __init__(self, client: AsyncElasticsearch):
        self.client = client
        self.index_manager = IndexManager(client)

    async def index_commit(self, commit: Commit) -> None:
        document = {
            "commit_hash": commit.github_sha,
            "message": commit.message,
            "metadata": {
                "author": commit.author_name,
                "date": commit.authored_date.isoformat(),
                "repository_id": commit.repository_id
            }
        }
        await self.client.index(
            index=self.index_manager.get_index_name('commits'),
            document=document,
            id=commit.github_sha
        )

    async def bulk_index_commits(self, commits: List[Commit]) -> None:
        actions = [
            {
                '_op_type': 'index',
                '_index': self.index_manager.get_index_name('commits'),
                '_id': commit.github_sha,
                '_source': {
                    "commit_hash": commit.github_sha,
                    "message": commit.message,
                    "metadata": {
                        "author": commit.author_name,
                        "date": commit.authored_date.isoformat(),
                        "repository_id": commit.repository_id
                    }
                }
            }
            for commit in commits
        ]
        
        if actions:
            success, failed = await async_bulk(
                self.client,
                actions,
                chunk_size=500,
                max_retries=3,
                yield_ok=False,
                raise_on_error=False
            )
            return success, failed

    async def index_issue(self, issue: Issue, comments: List[IssueComment] = None) -> None:
        document = {
            "issue_number": issue.number,
            "title": issue.title,
            "body": issue.body,
            "metadata": {
                "state": issue.state,
                "created_at": issue.created_at.isoformat(),
                "closed_at": issue.closed_at.isoformat() if issue.closed_at else None,
                "author": issue.author_login,
                "labels": issue.labels.split(",") if issue.labels else [],
                "repository_id": issue.repository_id
            }
        }
        
        if comments:
            document["comments"] = [
                {
                    "author": comment.author_login,
                    "content": comment.body,
                    "date": comment.created_at.isoformat()
                }
                for comment in comments
            ]

        await self.client.index(
            index=self.index_manager.get_index_name('issues'),
            document=document,
            id=f"{issue.repository_id}_{issue.number}"
        )

    async def bulk_index_issues(self, issues: List[Issue], comments_map: Dict[int, List[IssueComment]] = None) -> Tuple[int, int]:
        actions = []
        for issue in issues:
            issue_comments = comments_map.get(issue.id, []) if comments_map else []
            actions.append({
                '_op_type': 'index',
                '_index': self.index_manager.get_index_name('issues'),
                '_id': f"{issue.repository_id}_{issue.number}",
                '_source': {
                    "issue_number": issue.number,
                    "title": issue.title,
                    "body": issue.body,
                    "metadata": {
                        "state": issue.state,
                        "created_at": issue.created_at.isoformat(),
                        "closed_at": issue.closed_at.isoformat() if issue.closed_at else None,
                        "author": issue.author_login,
                        "labels": issue.labels.split(",") if issue.labels else [],
                        "repository_id": issue.repository_id
                    },
                    "comments": [
                        {
                            "author": comment.author_login,
                            "content": comment.body,
                            "date": comment.created_at.isoformat()
                        }
                        for comment in issue_comments
                    ]
                }
            })
        
        if actions:
            return await async_bulk(
                self.client,
                actions,
                chunk_size=500,
                max_retries=3,
                yield_ok=False,
                raise_on_error=False
            )
        return 0, 0

    async def index_pull_request(self, pr: PullRequest, comments: List[PullRequestComment] = None) -> None:
        document = {
            "pr_number": pr.number,
            "title": pr.title,
            "description": pr.body,
            "metadata": {
                "state": pr.state,
                "created_at": pr.created_at.isoformat(),
                "merged_at": pr.merged_at.isoformat() if pr.merged_at else None,
                "author": pr.author_login,
                "base_branch": pr.base_branch,
                "head_branch": pr.head_branch,
                "is_merged": pr.is_merged,
                "repository_id": pr.repository_id
            }
        }

        if comments:
            document["reviews"] = [
                {
                    "reviewer": comment.author_login,
                    "comment": comment.body,
                    "date": comment.created_at.isoformat(),
                    "is_initial": comment.is_initial
                }
                for comment in comments
            ]

        await self.client.index(
            index=self.index_manager.get_index_name('pull_requests'),
            document=document,
            id=f"{pr.repository_id}_{pr.number}"
        )

    async def bulk_index_pull_requests(self, prs: List[PullRequest], comments_map: Dict[int, List[PullRequestComment]] = None) -> Tuple[int, int]:
        actions = []
        for pr in prs:
            pr_comments = comments_map.get(pr.id, []) if comments_map else []
            actions.append({
                '_op_type': 'index',
                '_index': self.index_manager.get_index_name('pull_requests'),
                '_id': f"{pr.repository_id}_{pr.number}",
                '_source': {
                    "pr_number": pr.number,
                    "title": pr.title,
                    "description": pr.body,
                    "metadata": {
                        "state": pr.state,
                        "created_at": pr.created_at.isoformat(),
                        "merged_at": pr.merged_at.isoformat() if pr.merged_at else None,
                        "author": pr.author_login,
                        "base_branch": pr.base_branch,
                        "head_branch": pr.head_branch,
                        "is_merged": pr.is_merged,
                        "repository_id": pr.repository_id
                    },
                    "reviews": [
                        {
                            "reviewer": comment.author_login,
                            "comment": comment.body,
                            "date": comment.created_at.isoformat(),
                            "is_initial": comment.is_initial
                        }
                        for comment in pr_comments
                    ]
                }
            })
        
        if actions:
            return await async_bulk(
                self.client,
                actions,
                chunk_size=500,
                max_retries=3,
                yield_ok=False,
                raise_on_error=False
            )
        return 0, 0
