from typing import Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from backend.services.github_service import GitHubService
from backend.models.repository import Repository, Commit, Issue, PullRequest
from backend.db.database import save_repository, save_commit, save_issue, save_pull_request

class RepositoryService:
    def __init__(self):
        self.github = GitHubService()
        self.max_items = 30  # Limit items per entity type to avoid rate limits

    async def initialize_repository(self, session: AsyncSession, owner: str, repo: str) -> Tuple[Repository, int, int, int]:
        # Get repository data
        repo_data = await self.github.get_repository(owner, repo)
        repository = Repository.from_github_data(repo_data)
        await save_repository(session, repository)

        # Fetch and save commits (limited to max_items)
        commits_data = await self.github.get_commits(owner, repo, page=1, per_page=self.max_items)
        commits_count = 0
        for commit_data in commits_data:
            commit = Commit.from_github_data(commit_data, repository.id)
            await save_commit(session, commit)
            commits_count += 1

        # Fetch and save issues (limited to max_items)
        issues_data = await self.github.get_issues(owner, repo, page=1, per_page=self.max_items)
        issues_count = 0
        for issue_data in issues_data:
            # Skip pull requests that appear in issues endpoint
            if "pull_request" in issue_data:
                continue
            issue = Issue.from_github_data(issue_data, repository.id)
            await save_issue(session, issue)
            issues_count += 1

        # Fetch and save pull requests (limited to max_items)
        prs_data = await self.github.get_pull_requests(owner, repo, page=1, per_page=self.max_items)
        prs_count = 0
        for pr_data in prs_data:
            pr = PullRequest.from_github_data(pr_data, repository.id)
            await save_pull_request(session, pr)
            prs_count += 1

        # Mark repository as initialized
        repository.is_initialized = True
        await save_repository(session, repository)

        return repository, commits_count, issues_count, prs_count

repository_service = RepositoryService()
