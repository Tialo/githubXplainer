import logging
import re
from typing import List, Optional
from dataclasses import dataclass
from backend.models.repository import (
    Issue, IssueComment, Repository,
    RepositoryLanguage, ReadmeSummary
)
from backend.services.commit_summarizer import OllamaBackend, GeminiBackend, RepositoryContext
from backend.utils.logger import get_logger
from backend.config.settings import settings

logger = get_logger(__name__)
logger.setLevel(logging.INFO)

@dataclass
class PRCommentGroup:
    comments: List[IssueComment]
    total_size: int = 0

class PullRequestDiscussionSummarizer:
    def __init__(self, max_group_size: int = 25000, backend: str = None):
        self.max_group_size = max_group_size
        self.repo_context = None
        if backend is None:
            backend = settings.LLM_USE
        if backend == "ollama":
            self.content_backend = OllamaBackend(settings.LLM_PR_CONTENT_SUMMARIZER)
            self.final_backend = OllamaBackend(settings.LLM_PR_FINAL_SUMMARIZER)
        elif backend == "gemini":
            self.content_backend = GeminiBackend(settings.LLM_GEMINI_PR_MODEL)
            self.final_backend = GeminiBackend(settings.LLM_GEMINI_PR_MODEL)
        else:
            raise ValueError(f"Unsupported backend: {backend}")

    def clean_summary(self, summary: str) -> str:
        # Remove content between <think> tags
        return re.sub(r'<think>.*?</think>', '', summary, flags=re.DOTALL).strip()

    def set_repository_context(self, languages: List[RepositoryLanguage], readme_summary: Optional[ReadmeSummary], repo_path: str) -> None:
        self.repo_context = RepositoryContext(languages=languages, readme_summary=readme_summary, repo_path=repo_path)

    def batch_comments(self, comments: List[IssueComment]) -> List[PRCommentGroup]:
        groups = []
        current_group = []
        current_size = 0

        for comment in comments:
            comment_size = len(comment.body)
            if current_size + comment_size > self.max_group_size and current_group:
                groups.append(PRCommentGroup(comments=current_group, total_size=current_size))
                current_group = []
                current_size = 0
            
            current_group.append(comment)
            current_size += comment_size

        if current_group:
            groups.append(PRCommentGroup(comments=current_group, total_size=current_size))

        return groups

    async def summarize_comment_group(self, comment_group: PRCommentGroup, issue: Issue, prev_group_summary: str = None) -> str:
        with open('backend/prompts/pr_comments_summarizer.txt', 'r') as f:
            prompt_template = f.read()

        system_prompt = prompt_template.format(
            repo_name=self.repo_context.repo_path,
            languages=self.repo_context.get_languages_str(),
            description=self.repo_context.get_description_str(),
            pr_title=issue.title,
            pr_content=issue.body or "No message provided",
            prev_summary=prev_group_summary or "This is first segment"
        )

        content = "\n".join(f"{comment.author_login}: {comment.body}" for comment in comment_group.comments)
        summary = await self.content_backend.generate_content(
            system_prompt,
            f"Summarize these comments: {content}"
        )
        return self.clean_summary(summary)

    async def generate_final_summary(
        self,
        issue: Issue,
        comment_summaries: List[str]
    ) -> str:
        with open('backend/prompts/pr_discussion_summarizer.txt', 'r') as f:
            prompt_template = f.read()

        system_prompt = prompt_template.format(
            repo_name=self.repo_context.repo_path,
            languages=self.repo_context.get_languages_str(),
            description=self.repo_context.get_description_str(),
            pr_title=issue.title,
            pr_content=issue.body or "No message provided",
        )

        content = (f"Pull Request Description:\n{issue.body or 'No description provided'}\n\n"
                  f"Discussion Summaries:\n" + "\n".join(comment_summaries))

        summary = await self.final_backend.generate_content(
            system_prompt,
            f"Create discussion summary: {content}"
        )
        return self.clean_summary(summary)

    async def summarize_pull_request_discussion(
        self,
        issue: Issue,
        comments: List[IssueComment],
        languages: List[RepositoryLanguage],
        readme_summary: Optional[ReadmeSummary],
        repository: Repository
    ) -> str:
        repo_path = f"{repository.owner}/{repository.name}"
        logger.info(f"Summarizing PR #{issue.number} discussion in {repo_path}")
        
        self.set_repository_context(languages, readme_summary, repo_path)

        # Process comments in groups
        prev_summary = None
        comment_groups = self.batch_comments(comments)
        comment_summaries = []
        for group in comment_groups:
            logger.info(f"Processing comment group with {len(group.comments)} comments")
            summary = await self.summarize_comment_group(group, issue, prev_group_summary=prev_summary)
            prev_summary = summary
            comment_summaries.append(summary)

        # Generate final discussion summary
        logger.info("Generating final PR discussion summary")
        return await self.generate_final_summary(issue, comment_summaries)
