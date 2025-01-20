from typing import Dict, List, Optional
import httpx
import time
from backend.config.settings import settings

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
                    return response.json()
                except httpx.ConnectTimeout:
                    time.sleep(settings.retry_delay)
                except httpx.HTTPError as e:
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

    async def get_pull_requests(self, owner: str, repo: str, page: int = 1, per_page: int = 100) -> List[Dict]:
        """Fetch repository pull requests."""
        return await self._make_request(
            f"repos/{owner}/{repo}/pulls",
            params={"page": page, "per_page": per_page, "state": "all"}
        )

    async def get_issue_comments(self, owner: str, repo: str, issue_number: int) -> List[Dict]:
        """Fetch comments for an issue."""
        return await self._make_request(
            f"repos/{owner}/{repo}/issues/{issue_number}/comments"
        )

    async def get_pull_request_comments(self, owner: str, repo: str, pr_number: int) -> List[Dict]:
        """Fetch comments for a pull request."""
        return await self._make_request(
            f"repos/{owner}/{repo}/pulls/{pr_number}/comments"
        )
