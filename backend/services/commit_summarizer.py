import logging
from typing import List, Optional
from dataclasses import dataclass
from backend.models.repository import CommitDiff, RepositoryLanguage, ReadmeSummary, Repository
from ollama import Client
from datetime import datetime
import re
from backend.utils.logger import get_logger
from backend.config.settings import settings


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

class LLMSummarizer:
    def __init__(self, max_group_size: int = 25000):
        self.max_group_size = max_group_size
        self.repo_context = None

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

    def process_group(self, diff_group: CommitDiffGroup) -> str:
        with open('backend/prompts/diff_summarizer.txt', 'r') as f:
            prompt_template = f.read()

        system_prompt = prompt_template.format(
            repo_name=self.repo_context.repo_path,
            languages=self.repo_context.get_languages_str() if self.repo_context else "",
            description=self.repo_context.get_description_str() if self.repo_context else "",
        )

        content = "\n\n".join(d.diff_content for d in diff_group.commit_diffs)

        response = Client().chat(
            model=settings.LLM_DIFF_SUMMARIZER,
            messages=[
                {
                    'role': 'system',
                    'content': system_prompt
                },
                {
                    'role': 'user',
                    'content': f"Summarize these changes {content}"
                }
            ]
        )
        return self.clean_summary(response.message.content)

    def generate_final_summary(self, summaries: List[str]) -> str:
        with open('backend/prompts/chunks_summarizer.txt', 'r') as f:
            prompt_template = f.read()

        system_prompt = prompt_template.format(
            repo_name=self.repo_context.repo_path,
            languages=self.repo_context.get_languages_str() if self.repo_context else "",
            description=self.repo_context.get_description_str() if self.repo_context else "",
        )

        combined_summaries = "\n".join(summaries)
        response = Client().chat(
            model=settings.LLM_CHUNK_SUMMARIZER,
            messages=[
                {
                    'role': 'system',
                    'content': system_prompt
                },
                {
                    'role': 'user',
                    'content': f"Finalize the summary {combined_summaries}"
                }
            ]
        )
        return self.clean_summary(response.message.content)

    def summarize_commit(self, diffs: List[CommitDiff], languages: List[RepositoryLanguage] = None, readme_summary: ReadmeSummary = None, repository: Repository = None) -> str:
        repo_path = f"{repository.owner}/{repository.name}"
        log_info("Summarizing commit diffs, repo %s", repo_path)
        
        self.set_repository_context(languages, readme_summary, repo_path)
        
        filtered_diffs = self.filter_diffs(diffs)
        diff_groups = self.batch_diffs(filtered_diffs)
        
        group_summaries = []
        for group in diff_groups:
            log_info("Processing diff group of size %d", len(group.commit_diffs))
            summary = self.process_group(group)
            group_summaries.append(summary)

        log_info("Generated %d summaries", len(group_summaries))
        return self.generate_final_summary(group_summaries)
