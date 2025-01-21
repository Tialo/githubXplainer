from typing import Tuple, Optional, List, Dict
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from backend.services.github_service import GitHubService
from backend.models.repository import Repository, Commit, Issue, IssueComment, CommitDiff, DeletedIssue
from backend.db.database import (
    save_repository, save_commit, save_issue,
    save_issue_comment, save_commit_diff,
    get_last_commit_with_null_parent, get_commit_by_sha,
    get_last_issue_with_null_parent, get_issue_by_number,
    get_repository_by_owner_and_name, update_repository_attributes,
    update_commit_attributes, get_deleted_issue_by_number,
    save_deleted_issue
)

class RepositoryService:
    def __init__(self):
        self.github = GitHubService()
        self.max_items = 10
        self.update_fetch_items = 5

    async def _process_commits_batch(
        self,
        session: AsyncSession,
        commits_data: List[Dict],
        repository: Repository,
        raise_=0
    ) -> int:
        """Process a batch of commits and return the count of new commits."""
        commits_count = 0
        for i, commit_data in enumerate(commits_data):
            existing_commit = await get_commit_by_sha(session, commit_data["sha"], repository.id)
            if i == 0 and existing_commit and existing_commit.parent_sha is None:
                await update_commit_attributes(session, existing_commit.id, parent_sha=commit_data["parents"][0]["sha"] if "parents" in commit_data else None)
            if existing_commit:
                continue

            # Set null parent for the last commit in the batch if it's new
            is_last = i + 1 == len(commits_data)
            commit = Commit.from_github_data(commit_data, repository.id, set_null_parent=is_last)
            await save_commit(session, commit)

            # Save commit diffs
            commit_detail = await self.github.get_commit(
                repository.owner, repository.name, commit_data["sha"]
            )
            if "files" in commit_detail:
                for file_diff in commit_detail["files"]:
                    diff = CommitDiff.from_github_data(
                        commit_id=commit.id,
                        file_diff=file_diff,
                    )
                    await save_commit_diff(session, diff)
            
            commits_count += 1
        return commits_count
    
    async def _process_issue(
        self,
        session: AsyncSession,
        issue_data: Dict,
        repository: Repository,
    ) -> Tuple[Issue, int]:
        """Process an issue and return the issue and count of new comments."""
        existing_issue = await get_issue_by_number(session, issue_data["number"], repository.id)
        if existing_issue:
            return existing_issue, 0
        
        issue = Issue.from_github_data(issue_data, repository.id)
        issue = await save_issue(session, issue)
        
        comments = await self.github.get_issue_comments(repository.owner, repository.name, issue.number)
        comments_count = 0
        for comment_data in comments:
            comment = IssueComment.from_github_data(comment_data, issue.id)
            await save_issue_comment(session, comment)
            comments_count += 1
    
        return issue, comments_count
    
    async def _process_issues_batch(
        self,
        session: AsyncSession,
        issues_data: List[Dict],
        repository: Repository,
    ) -> int:
        """Process a batch of issues and return the count of new issues."""
        issues_count = 0
        for issue_data in issues_data:
            await self._process_issue(session, issue_data, repository)
            issues_count += 1
        return issues_count

    async def _initialize_repository(self, session: AsyncSession, repository: Repository) -> Tuple[Repository, int, int]:
        owner, repo = repository.owner, repository.name

        # Fetch and save commits (limited to max_items)
        commits_data = await self.github.get_commits(
            owner, repo, page=1, per_page=self.max_items
        )
        commits_count = await self._process_commits_batch(
            session, commits_data, repository
        )

        # Fetch and save issues with comments
        issues_data = await self.github.get_issues(owner, repo, page=1, per_page=self.max_items)
        issues_count = 0
        for issue_data in issues_data:
            issue = Issue.from_github_data(issue_data, repository.id)
            issue = await save_issue(session, issue)
            
            # Fetch and save issue comments
            comments = await self.github.get_issue_comments(owner, repo, issue.number)
            for comment_data in comments:
                comment = IssueComment.from_github_data(comment_data, issue.id)
                await save_issue_comment(session, comment)
            
            issues_count += 1

        # Update repository initialization status using the new function
        repository = await update_repository_attributes(
            session, 
            repository.id, 
            is_initialized=True
        )

        return repository, commits_count, issues_count

    async def update_repository(self, session: AsyncSession, owner: str, repo: str) -> Tuple[Repository, int, int]:
        async with session.begin():
            # Get repository data
            repo_data = await self.github.get_repository(owner, repo)
            
            # Check if repository exists
            existing_repository = await get_repository_by_owner_and_name(session, owner, repo)
            repository = Repository.from_github_data(repo_data)
            
            if existing_repository:
                repository = existing_repository
            else:
                repository = await save_repository(session, repository)

            if not repository.is_initialized:
                return await self._initialize_repository(session, repository)

            # Fetch recent commits
            recent_commits = await self.github.get_commits(
                owner, repo, page=1, per_page=self.update_fetch_items
            )
            commits_count = await self._process_commits_batch(
                session, recent_commits, repository
            )

            # Find the last commit with null parent_sha
            recent_orphan_commit = await get_last_commit_with_null_parent(session, repository.id)
            if recent_orphan_commit:
                # Fetch commits before orphan commit
                before_commits = await self.github.get_commits_before_sha(
                    owner, repo, recent_orphan_commit.github_sha, page=1, per_page=self.update_fetch_items
                )
                commits_count += await self._process_commits_batch(
                    session, before_commits, repository, raise_=1
                )

            # Fetch recent issues
            recent_issues = await self.github.get_issues(owner, repo, page=1, per_page=self.max_items)
            issues_count = await self._process_issues_batch(
                session, recent_issues, repository
            )

            # Find the last issue with null parent
            recent_orphan_issue = await get_last_issue_with_null_parent(session, repository.id)
            if recent_orphan_issue:
                # Fetch issues before orphan issue
                for i in range(1, min(self.update_fetch_items + 1, recent_orphan_issue.number)):
                    # use min to avoid fetching issues with not positive numbers
                    before_issue = await get_issue_by_number(session, recent_orphan_issue.number - i, repository.id)
                    if before_issue:
                        continue
                    before_issue = await self.github.get_issue_by_number(
                        owner, repo, number=recent_orphan_issue.number - i
                    )
                    if before_issue:
                        await self._process_issue(session, before_issue, repository)
                        issues_count += 1
                        continue
                    
                    # if issue wasn't found on GitHub, then it was deleted by repository owner
                    deleted_issue = await get_deleted_issue_by_number(
                        session, recent_orphan_issue.number - i, repository.id
                    )
                    if deleted_issue:
                        issues_count += 1
                    else:
                        await save_deleted_issue(
                            session, DeletedIssue(
                                number=recent_orphan_issue.number - i,
                                repository_id=repository.id
                            )
                        )

            return repository, commits_count, issues_count

    async def get_all_repositories(self, session: AsyncSession):
        """Get all repositories from the database."""
        result = await session.execute(select(Repository))
        return result.scalars().all()

    async def get_all_initialized_repositories(self, session: AsyncSession):
        """Get all initialized repositories from the database."""
        result = await session.execute(
            select(Repository).where(Repository.is_initialized == True)
        )
        return result.scalars().all()

    async def delete_repository(self, session: AsyncSession, owner: str, repo: str) -> Repository:
        """Delete a repository and all its associated data."""
        async with session.begin():
            # Get repository
            repository = await get_repository_by_owner_and_name(session, owner, repo)
            if not repository:
                raise ValueError(f"Repository {owner}/{repo} not found")
            
            # Delete all related data
            await session.execute(
                text("""
                WITH deleted_issues AS (
                    DELETE FROM issues WHERE repository_id = :repo_id RETURNING id
                )
                DELETE FROM issue_comments WHERE issue_id IN (SELECT id FROM deleted_issues)
                """),
                {"repo_id": repository.id}
            )
            
            await session.execute(
                text("""
                WITH deleted_commits AS (
                    DELETE FROM commits WHERE repository_id = :repo_id RETURNING id
                )
                DELETE FROM commit_diffs WHERE commit_id IN (SELECT id FROM deleted_commits)
                """),
                {"repo_id": repository.id}
            )
            
            # Delete deleted_issues records
            await session.execute(
                text("DELETE FROM deleted_issues WHERE repository_id = :repo_id"),
                {"repo_id": repository.id}
            )
            
            # Delete the repository itself
            await session.execute(
                text("DELETE FROM repositories WHERE id = :repo_id"),
                {"repo_id": repository.id}
            )
            
            await session.commit()
            return repository

repository_service = RepositoryService()
