from typing import Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from backend.services.github_service import GitHubService
from backend.models.repository import Repository, Commit, Issue, IssueComment, PullRequest, PullRequestComment
from backend.db.database import (
    save_repository, save_commit, save_issue, save_pull_request,
    save_issue_comment, save_pr_comment
)

class RepositoryService:
    def __init__(self):
        self.github = GitHubService()
        self.max_items = 20  # Limit items per entity type to avoid rate limits
        self.max_comments = 10  # Limit comments per issue/PR

    async def initialize_repository(self, session: AsyncSession, owner: str, repo: str) -> Tuple[Repository, int, int, int]:
        async with session.begin():
            # Get repository data
            repo_data = await self.github.get_repository(owner, repo)
            repository = Repository.from_github_data(repo_data)
            repository = await save_repository(session, repository)

            # Fetch and save commits (limited to max_items)
            commits_data = await self.github.get_commits(owner, repo, page=1, per_page=self.max_items)
            commits_count = 0
            for commit_data in commits_data:
                commit = Commit.from_github_data(commit_data, repository.id)
                await save_commit(session, commit)
                commits_count += 1

            # Fetch and save issues with comments
            issues_data = await self.github.get_issues(owner, repo, page=1, per_page=self.max_items)
            issues_count = 0
            for issue_data in issues_data:
                # Skip pull requests that appear in issues endpoint
                if "pull_request" in issue_data:
                    continue
                issue = Issue.from_github_data(issue_data, repository.id)
                issue = await save_issue(session, issue)
                
                # Fetch and save issue comments
                comments = await self.github.get_issue_comments(owner, repo, issue.number)
                for comment_data in comments[:self.max_comments]:
                    comment = IssueComment.from_github_data(comment_data, issue.id)
                    await save_issue_comment(session, comment)
                
                issues_count += 1

            # Fetch and save pull requests with comments
            prs_data = await self.github.get_pull_requests(owner, repo, page=1, per_page=self.max_items)
            prs_count = 0
            for pr_data in prs_data:
                pr = PullRequest.from_github_data(pr_data, repository.id)
                pr = await save_pull_request(session, pr)
                
                # Save PR description as initial comment
                initial_comment = PullRequestComment.from_github_data(pr_data, pr.id, is_initial=True)
                await save_pr_comment(session, initial_comment)
                
                # Fetch and save PR comments
                comments = await self.github.get_pull_request_comments(owner, repo, pr.number)
                for comment_data in comments[:self.max_comments]:
                    comment = PullRequestComment.from_github_data(comment_data, pr.id)
                    await save_pr_comment(session, comment)
                
                prs_count += 1

            # Update repository initialization status
            repository.is_initialized = True
            repository = await save_repository(session, repository)

            return repository, commits_count, issues_count, prs_count

repository_service = RepositoryService()
