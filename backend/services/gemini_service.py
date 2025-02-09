from google import genai
from backend.config.settings import settings
from backend.utils.logger import get_logger
from backend.models.repository import Repository, Commit
import os

logger = get_logger(__name__)

class GeminiService:
    def __init__(self):
        self.client = genai.Client(api_key=settings.gemini_api_key)
        
        # Load the prompt template
        prompt_path = os.path.join(os.path.dirname(__file__), '../prompts/question_answer.txt')
        with open(prompt_path, 'r') as f:
            self.prompt_template = f.read()

    async def summarize_results(
        self,
        query: str,
        results: list,
        commits: list[Commit],
        repository: Repository,
        model_name: str = "gemini-2.0-flash-exp"
    ) -> str:
        commit_summaries = []
        
        # Then format the results with commit links only for relevant commits
        for result, commit in zip(results, commits):
            content = result.page_content
            commit_hash = commit.github_sha
            commit_link = f"https://github.com/{repository.owner}/{repository.name}/commit/{commit_hash}"
            content = f"{content}\nCommit: {commit_link}"
            commit_summaries.append(content)

        # raise ValueError("\n\n".join(commit_summaries))

        # Format the prompt
        prompt = self.prompt_template.format(
            user_query=query,
            commit_summaries_with_links="\n\n".join(commit_summaries)
        )

        response = await self.client.aio.models.generate_content(model=model_name, contents=prompt)
        return response.text, prompt

gemini_service = GeminiService()
