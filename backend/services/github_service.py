import logging
from typing import Dict, List, Optional
import httpx
import time
from backend.config.settings import settings

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class GitHubService:
    def __init__(self):
        self.base_url = settings.github_api_url
        self.headers = {
            "Authorization": f"token {settings.github_token}",
            "Accept": "application/vnd.github.v3+json"
        }

    async def _make_request(self, endpoint: str, method: str = "GET", params: Optional[Dict] = None) -> Dict:
        async with httpx.AsyncClient() as client:
            for attempt in range(settings.max_retries):
                response = None
                try:
                    response = await client.request(
                        method,
                        f"{self.base_url}/{endpoint}",
                        headers=self.headers,
                        params=params
                    )
                    response.raise_for_status()
                    time.sleep(settings.success_delay)
                    return response.json()
                except httpx.ConnectTimeout:
                    logger.info(f"Request timed out. Retrying in {settings.retry_delay} seconds.")
                    time.sleep(settings.retry_delay)
                except httpx.HTTPError:
                    if attempt == settings.max_retries - 1:
                        raise
                    if response and response.status_code == 403 and "rate limit" in response.text.lower():
                        time.sleep(settings.retry_delay)
                        continue
                    raise

    async def get_repository(self, owner: str, repo: str) -> Dict:
        """Fetch repository information."""
        return await self._make_request(f"repos/{owner}/{repo}")

    async def get_commits(self, owner: str, repo: str, page: int = 1, per_page: int = 100) -> List[Dict]:
        """Fetch repository commits."""
        return await self._make_request(
            f"repos/{owner}/{repo}/commits",
            params={"page": page, "per_page": per_page}
        )

    async def get_issues(self, owner: str, repo: str, page: int = 1, per_page: int = 100) -> List[Dict]:
        """Fetch repository issues."""
        return await self._make_request(
            f"repos/{owner}/{repo}/issues",
            params={"page": page, "per_page": per_page, "state": "all"}
        )

    async def get_issue_comments(self, owner: str, repo: str, issue_number: int) -> List[Dict]:
        """Fetch comments for an issue."""
        return await self._make_request(
            f"repos/{owner}/{repo}/issues/{issue_number}/comments"
        )
        
    async def get_commit(self, owner: str, repo: str, commit_sha: str) -> dict:
        """Fetch detailed information about a specific commit."""
        return await self._make_request(
            f"repos/{owner}/{repo}/commits/{commit_sha}"
        )

    async def get_issue_by_number(self, owner: str, repo: str, number: int) -> Optional[Dict]:
        """Fetch a specific issue by its number."""
        try:
            return await self._make_request(f"repos/{owner}/{repo}/issues/{number}")
        except httpx.HTTPStatusError as e:
            # some deleted issues return 404, some return 410
            if e.response.status_code in [404, 410]:
                return None
            raise

    async def get_commits_before_sha(self, owner: str, repo: str, sha: str, page: int = 1, per_page: int = 100) -> List[Dict]:
        """Fetch commits before the specified SHA."""
        return await self._make_request(
            f"repos/{owner}/{repo}/commits",
            params={"sha": sha, "per_page": per_page, "page": page}
        )
