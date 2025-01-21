from typing import List
from dataclasses import dataclass
from backend.models.repository import CommitDiff
from ollama import Client
import re

@dataclass
class DiffGroup:
    content: str
    size: int

class LLMSummarizer:
    def __init__(self, max_group_size: int = 5000):
        self.max_group_size = max_group_size

    def filter_diffs(self, diffs: List[CommitDiff]) -> List[CommitDiff]:
        return [diff for diff in diffs if not diff.file_path.endswith('.lock')]

    def batch_diffs(self, diffs: List[CommitDiff]) -> List[DiffGroup]:
        groups = []
        current_group = []
        current_size = 0

        for diff in diffs:
            diff_size = len(diff.content)
            
            if current_size + diff_size > self.max_group_size and current_group:
                groups.append(DiffGroup(
                    content='\n'.join(current_group),
                    size=current_size
                ))
                current_group = []
                current_size = 0
            
            current_group.append(diff.content)
            current_size += diff_size

        if current_group:
            groups.append(DiffGroup(
                content='\n'.join(current_group),
                size=current_size
            ))

        return groups

    def clean_summary(self, summary: str) -> str:
        # Remove content between <think> tags
        return re.sub(r'<think>.*?</think>', '', summary, flags=re.DOTALL).strip()

    def process_group(self, diff_group: DiffGroup) -> str:
        prompt = """Analyze this git diff and provide a short, concise summary of the changes:

{content}

Provide only the key changes and their impact."""

        response = Client().chat(
            model='deepseek-r1:8b',
            messages=[{
                'role': 'user',
                'content': prompt.format(content=diff_group.content)
            }]
        )
        return self.clean_summary(response.message.content)

    def generate_final_summary(self, summaries: List[str]) -> str:
        combined_summaries = "\n".join(summaries)
        prompt = """Based on these individual change summaries, provide a concise, coherent summary of all changes:

{summaries}

Focus on the overall impact and main changes."""

        response = Client.chat(
            model='deepseek-r1:14b',
            messages=[{
                'role': 'user',
                'content': prompt.format(summaries=combined_summaries)
            }]
        )
        return self.clean_summary(response.message.content)

    def summarize_commit(self, diffs: List[CommitDiff]) -> str:
        filtered_diffs = self.filter_diffs(diffs)
        diff_groups = self.batch_diffs(filtered_diffs)
        
        group_summaries = []
        for group in diff_groups:
            summary = self.process_group(group)
            group_summaries.append(summary)

        return self.generate_final_summary(group_summaries)
