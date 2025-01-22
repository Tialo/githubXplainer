from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from backend.config.settings import settings
from langchain_community.docstore.in_memory import InMemoryDocstore
import os
import time
import faiss
from langchain_core.documents import Document

class VectorStore:
    def __init__(self):
        self.embeddings = OpenAIEmbeddings(api_key=settings.OPENAI_API_KEY, openai_api_base=settings.OPENAI_API_BASE)
        self.index = faiss.IndexFlatL2(len(self.embeddings.embed_query("123")))
        self.store_path = "vector_store"
        self._load_or_create_store()

    def _load_or_create_store(self):
        if os.path.exists(self.store_path):
            self.store = FAISS.load_local(self.store_path, self.embeddings, allow_dangerous_deserialization=True)
        else:
            self.store = FAISS(
                self.embeddings,
                index=self.index,
                docstore=InMemoryDocstore(),
                index_to_docstore_id={},
            )
            self.store.save_local(self.store_path)

    def add_summary(self, text: str, metadata: dict):
        self.store.add_documents(
            [Document(text, metadata=metadata)],
        )
        now = time.time()
        self.store.save_local(self.store_path)
        print(time.time() - now, "FAISS SAVED IN")

    def search_similar(self, query: str, k: int = 5):
        return self.store.similarity_search(query, k=k)
