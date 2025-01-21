from elasticsearch import AsyncElasticsearch
from elasticsearch.helpers import async_scan
from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings
import ssl
import certifi

class ElasticsearchSettings(BaseSettings):
    elasticsearch_url: str = "http://localhost:9200"
    elasticsearch_username: Optional[str] = None
    elasticsearch_password: Optional[str] = None
    index_prefix: str = "githubxplainer"

    class Config:
        env_prefix = "ES_"

@lru_cache()
def get_elasticsearch_settings() -> ElasticsearchSettings:
    return ElasticsearchSettings()

async def get_elasticsearch_client() -> AsyncElasticsearch:
    settings = get_elasticsearch_settings()
    return AsyncElasticsearch(
        hosts=[settings.elasticsearch_url],
        basic_auth=(settings.elasticsearch_username, settings.elasticsearch_password) 
        if settings.elasticsearch_username else None,
        verify_certs=True,
        ssl_context=ssl.create_default_context(cafile=certifi.where()),
        request_timeout=30
    )
