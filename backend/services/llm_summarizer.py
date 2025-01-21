from typing import List, Optional
from dataclasses import dataclass
from backend.models.repository import CommitDiff, RepositoryLanguage, ReadmeSummary
from ollama import Client
import re


@dataclass
class CommitDiffGroup:
    commit_diffs: List[CommitDiff]

@dataclass
class RepositoryContext:
    languages: List[RepositoryLanguage]
    readme_summary: Optional[ReadmeSummary]

    def get_languages_str(self) -> str:
        return ", ".join(lang.language for lang in self.languages)

    def get_domain_str(self) -> str:
        return self.readme_summary.summarization if self.readme_summary else "No domain information available"

class LLMSummarizer:
    def __init__(self, max_group_size: int = 5000):
        self.max_group_size = max_group_size
        self.repo_context = None

    def filter_diffs(self, diffs: List[CommitDiff]) -> List[CommitDiff]:
        return [diff for diff in diffs if not diff.file_path.endswith('.lock')]

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
            
            current_group.append(diff.content)
            current_size += diff_size

        if current_group:
            groups.append(CommitDiffGroup(
                commit_diffs=current_group
            ))

        return groups

    def clean_summary(self, summary: str) -> str:
        # Remove content between <think> tags
        return re.sub(r'<think>.*?</think>', '', summary, flags=re.DOTALL).strip()

    def set_repository_context(self, languages: List[RepositoryLanguage], readme_summary: Optional[ReadmeSummary]) -> None:
        self.repo_context = RepositoryContext(languages=languages, readme_summary=readme_summary)

    def process_group(self, diff_group: CommitDiffGroup) -> str:
        with open('backend/prompts/diff_summarizer.txt', 'r') as f:
            prompt_template = f.read()

        context = {
            'content': "\n".join(d.diff_content for d in diff_group.commit_diffs),
            'languages': self.repo_context.get_languages_str() if self.repo_context else "",
            'domain': self.repo_context.get_domain_str() if self.repo_context else "",
        }

        response = Client().chat(
            model='deepseek-r1:8b',
            messages=[{
                'role': 'user',
                'content': prompt_template.format(**context)
            }]
        )
        return self.clean_summary(response.message.content)

    def generate_final_summary(self, summaries: List[str]) -> str:
        with open('backend/prompts/chunks_summarizer.txt', 'r') as f:
            prompt_template = f.read()

        combined_summaries = "\n".join(summaries)
        response = Client.chat(
            model='deepseek-r1:14b',
            messages=[{
                'role': 'user',
                'content': prompt_template.format(
                    summaries=combined_summaries
                )
            }]
        )
        return self.clean_summary(response.message.content)

    def summarize_commit(self, diffs: List[CommitDiff], languages: List[RepositoryLanguage] = None, readme_summary: ReadmeSummary = None) -> str:
        if languages is not None and readme_summary is not None:
            self.set_repository_context(languages, readme_summary)
        
        filtered_diffs = self.filter_diffs(diffs)
        diff_groups = self.batch_diffs(filtered_diffs)
        
        group_summaries = []
        for group in diff_groups:
            summary = self.process_group(group)
            group_summaries.append(summary)

        return self.generate_final_summary(group_summaries)
