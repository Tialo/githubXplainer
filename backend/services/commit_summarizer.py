import logging
from typing import List, Optional
from dataclasses import dataclass
from backend.models.repository import CommitDiff, RepositoryLanguage, ReadmeSummary, Repository, Commit, Issue, PullRequestSummary
from ollama import AsyncClient
from datetime import datetime
import re
import asyncio
from backend.utils.logger import get_logger
from backend.config.settings import settings
from abc import ABC, abstractmethod
from google import genai

logger = get_logger(__name__)
logger.setLevel(logging.INFO)

def log_info(text, *params):
    print(f"[{datetime.now()}] {text % params}")

def log_error(text, *params):
    print(f"[{datetime.now()}] ERROR: {text % params}")


@dataclass
class CommitDiffGroup:
    commit_diffs: List[CommitDiff]

@dataclass
class RepositoryContext:
    languages: List[RepositoryLanguage]
    readme_summary: Optional[ReadmeSummary]
    repo_path: str

    def get_languages_str(self) -> str:
        if not self.languages:
            return ""
            
        # Sort languages by bytes and calculate total
        sorted_langs = sorted(self.languages, key=lambda x: x.bytes_count, reverse=True)
        total_bytes = sum(lang.bytes_count for lang in self.languages)
        
        # Take top 5 languages and normalize percentages
        top_langs = sorted_langs[:5]
        lang_percentages = [
            f"{lang.language} ({(lang.bytes_count/total_bytes)*100:.1f}%)"
            for lang in top_langs
        ]
        
        return ", ".join(lang_percentages)

    def get_description_str(self) -> str:
        return self.readme_summary.summarization if self.readme_summary else "No domain information available"

class ModelBackend(ABC):
    @abstractmethod
    async def generate_content(self, system_prompt: str, user_content: str) -> str:
        pass

class OllamaBackend(ModelBackend):
    def __init__(self, model_name: str):
        self.client = AsyncClient()
        self.model_name = model_name

    async def generate_content(self, system_prompt: str, user_content: str) -> str:
        response = await self.client.chat(
            model=self.model_name,
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_content}
            ]
        )
        return response.message.content

class GeminiBackend(ModelBackend):
    def __init__(self, model_name: str):
        self.client = genai.Client(api_key=settings.gemini_api_key)
        self.model_name = model_name

    async def generate_content(self, system_prompt: str, user_content: str) -> str:
        combined_prompt = f"{system_prompt}\n\n{user_content}"
        for _ in range(3):
            try:
                response = await self.client.aio.models.generate_content(
                    model=self.model_name,
                    contents=combined_prompt
                )
                continue
            except:
                await asyncio.sleep(15)
        return response.text

class LLMSummarizer:
    def __init__(self, max_group_size: int = 25000, backend: str = None ):
        self.max_group_size = max_group_size
        self.repo_context = None
        if backend is None:
            backend = settings.LLM_USE
        if backend == "ollama":
            self.diff_backend = OllamaBackend(settings.LLM_DIFF_SUMMARIZER)
            self.chunk_backend = OllamaBackend(settings.LLM_CHUNK_SUMMARIZER)
        elif backend == "gemini":
            self.diff_backend = GeminiBackend(settings.LLM_GEMINI_DIFF_MODEL)
            self.chunk_backend = GeminiBackend(settings.LLM_GEMINI_CHUNK_MODEL)
        else:
            raise ValueError(f"Unsupported backend: {backend}")

    def filter_diffs(self, diffs: List[CommitDiff]) -> List[CommitDiff]:
        return [diff for diff in diffs if not diff.file_path.endswith('.lock') and diff.diff_content]

    def batch_diffs(self, diffs: List[CommitDiff]) -> List[CommitDiffGroup]:
        groups = []
        current_group = []
        current_size = 0

        for diff in diffs:
            diff_size = len(diff.diff_content)
            
            if current_size + diff_size > self.max_group_size and current_group:
                groups.append(CommitDiffGroup(
                    commit_diffs=current_group
                ))
                current_group = []
                current_size = 0
            
            current_group.append(diff)
            current_size += diff_size

        if current_group:
            groups.append(CommitDiffGroup(
                commit_diffs=current_group
            ))

        return groups

    def clean_summary(self, summary: str) -> str:
        # Remove content between <think> tags
        return re.sub(r'<think>.*?</think>', '', summary, flags=re.DOTALL).strip()

    def set_repository_context(self, languages: List[RepositoryLanguage], readme_summary: Optional[ReadmeSummary], repo_path: str) -> None:
        self.repo_context = RepositoryContext(languages=languages, readme_summary=readme_summary, repo_path=repo_path)

    async def process_group(self, diff_group: CommitDiffGroup, commit_message: str) -> str:
        with open('backend/prompts/diff_summarizer.txt', 'r') as f:
            prompt_template = f.read()

        system_prompt = prompt_template.format(
            repo_name=self.repo_context.repo_path,
            languages=self.repo_context.get_languages_str() if self.repo_context else "",
            description=self.repo_context.get_description_str() if self.repo_context else "",
            commit_message=commit_message,
        )

        content = "\n\n".join(d.diff_content for d in diff_group.commit_diffs)
        summary = await self.diff_backend.generate_content(
            system_prompt,
            f"Summarize these changes {content}"
        )
        return self.clean_summary(summary)

    async def generate_final_summary(self, summaries: List[str], commit_message: str, pr: Optional[Issue] = None, pr_summary: Optional[PullRequestSummary] = None) -> str:
        if pr is None:
            with open('backend/prompts/chunk_summarizer.txt', 'r') as f:
                prompt_template = f.read()
                additional_params = {}
        else:
            with open('backend/prompts/chunk_summarizerv2.txt', 'r') as f:
                prompt_template = f.read()
            additional_params = {"pr_title": pr.title, "pr_content": pr.body or "No message provided"}
            if pr_summary:
                additional_params["pr_summary"] = pr_summary.summarization
            else:
                additional_params["pr_summary"] = "No summary provided"

        system_prompt = prompt_template.format(
            repo_name=self.repo_context.repo_path,
            languages=self.repo_context.get_languages_str() if self.repo_context else "",
            description=self.repo_context.get_description_str() if self.repo_context else "",
            commit_message=commit_message,
            **additional_params,
        )

        combined_summaries = "\n".join(summaries)
        summary = await self.chunk_backend.generate_content(
            system_prompt,
            f"Finalize the summary {combined_summaries}"
        )
        return self.clean_summary(summary)

    async def summarize_commit(
        self,
        commit: Commit,
        diffs: List[CommitDiff],
        languages: List[RepositoryLanguage] = None,
        readme_summary: ReadmeSummary = None,
        repository: Repository = None,
        pr: Optional[Issue] = None,
        pr_summary: Optional[PullRequestSummary] = None
    ) -> str:
        repo_path = f"{repository.owner}/{repository.name}"
        log_info("Summarizing commit diffs, repo %s", repo_path)
        
        self.set_repository_context(languages, readme_summary, repo_path)
        
        filtered_diffs = self.filter_diffs(diffs)
        diff_groups = self.batch_diffs(filtered_diffs)
        
        group_summaries = []
        for group in diff_groups:
            log_info("Processing diff group of size %d", len(group.commit_diffs))
            summary = await self.process_group(group, commit.message)
            group_summaries.append(summary)

        log_info("Generated %d summaries", len(group_summaries))
        return await self.generate_final_summary(group_summaries, commit.message, pr=pr, pr_summary=pr_summary)


if __name__ == "__main__":
    summarizer = LLMSummarizer(
        backend="ollama"
    )
    from sqlalchemy.sql import text

    async def test_summarizer():
        from backend.config.settings import async_session
        from backend.services.summary_generator import CommitNotFoundError, get_commit_data

        async with async_session() as session:
            commit_id = 1
            try:
                commit, diffs, pr, languages, readme_summary, repository = await get_commit_data(session, commit_id)
            except CommitNotFoundError:
                log_error("Commit with id %d not found", commit_id)
                return

            summary = await summarizer.summarize_commit(commit, diffs, languages, readme_summary, repository)
            log_info("Summary for commit %d: %s", commit_id, summary)

    # asyncio.run(test_summarizer())

    async def delete_commit_summaries():
        from backend.config.settings import async_session
        async with async_session() as session:
            result = await session.execute(
                text("delete FROM commit_summaries")
            )
            await session.commit()

    asyncio.run(delete_commit_summaries())
