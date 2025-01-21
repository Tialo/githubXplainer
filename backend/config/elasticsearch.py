from elasticsearch import AsyncElasticsearch
from pydantic_settings import BaseSettings
import ssl
import certifi

class ElasticsearchSettings(BaseSettings):
    host: str = "localhost"
    port: int = 9200
    index_prefix: str = "github"

    class Config:
        env_prefix = "ES_"

def get_elasticsearch_settings() -> ElasticsearchSettings:
    return ElasticsearchSettings()

def create_elasticsearch_client() -> AsyncElasticsearch:
    settings = get_elasticsearch_settings()
    return AsyncElasticsearch(
        hosts=[f'http://{settings.host}:{settings.port}'],
        verify_certs=False,  # Modified for local development
        request_timeout=30
    )

async def get_elasticsearch_client() -> AsyncElasticsearch:
    client = create_elasticsearch_client()
    # Test the connection
    await client.info()
    return client
