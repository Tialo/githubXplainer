from ollama import chat
from backend.config.settings import settings
import os
import re

class ReadmeSummarizer:
    def __init__(self):
        self.prompt_path = os.path.join(
            os.path.dirname(__file__), 
            "..", 
            "prompts",
            "readme_summarizer.txt"
        )
        with open(self.prompt_path, 'r') as f:
            self.prompt_template = f.read()

    def summarize(self, readme_content: str) -> str:
        prompt = f"{self.prompt_template}\n\nAnalyze this README content:\n\n{readme_content}"
    
        response = chat(
            model=settings.LLM_README_SUMMARIZER,
            messages=[{
                'role': 'user',
                'content': prompt
            }]
        )

        return self.clean_summary(response.message.content)

    def clean_summary(self, summary: str) -> str:
        # Remove content between <think> tags
        return re.sub(r'<think>.*?</think>', '', summary, flags=re.DOTALL).strip()
