from celery import shared_task
from backend.config.elasticsearch import get_elasticsearch_client
from backend.services.elasticsearch.indexer import Indexer
from backend.models.repository import Commit, Issue, PullRequest, IssueComment, PullRequestComment
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3)
async def sync_repository_data(self, repository_id: int):
    try:
        client = await get_elasticsearch_client()
        indexer = Indexer(client)

        async with AsyncSession() as session:
            # Sync commits
            commits = await session.execute(
                select(Commit).filter(Commit.repository_id == repository_id)
            )
            commits = commits.scalars().all()
            await indexer.bulk_index_commits(commits)

            # Sync issues with comments
            issues = await session.execute(
                select(Issue).filter(Issue.repository_id == repository_id)
            )
            issues = issues.scalars().all()
            
            issue_comments = await session.execute(
                select(IssueComment).filter(IssueComment.issue_id.in_([i.id for i in issues]))
            )
            comments_map = {}
            for comment in issue_comments.scalars():
                comments_map.setdefault(comment.issue_id, []).append(comment)
            
            await indexer.bulk_index_issues(issues, comments_map)

            # Sync pull requests with comments
            prs = await session.execute(
                select(PullRequest).filter(PullRequest.repository_id == repository_id)
            )
            prs = prs.scalars().all()
            
            pr_comments = await session.execute(
                select(PullRequestComment).filter(PullRequestComment.pull_request_id.in_([pr.id for pr in prs]))
            )
            pr_comments_map = {}
            for comment in pr_comments.scalars():
                pr_comments_map.setdefault(comment.pull_request_id, []).append(comment)
            
            await indexer.bulk_index_pull_requests(prs, pr_comments_map)

    except Exception as exc:
        logger.error(f"Error syncing repository {repository_id}: {exc}")
        raise self.retry(exc=exc)
