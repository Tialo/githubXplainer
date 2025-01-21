from ollama import chat
import os

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
            model='deepseek-r1:8b',
            messages=[{
                'role': 'user',
                'content': prompt
            }]
        )

        return response.message.content
