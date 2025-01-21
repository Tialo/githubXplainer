from elasticsearch import AsyncElasticsearch
from backend.config.elasticsearch import get_elasticsearch_settings
from typing import Dict, Any, List
import json
import os
import logging

logger = logging.getLogger(__name__)

class IndexManager:
    def __init__(self, client: AsyncElasticsearch):
        self.client = client
        self.settings = get_elasticsearch_settings()
        
    def get_index_name(self, base_name: str) -> str:
        return f"{self.settings.index_prefix}_{base_name}"

    async def ensure_indices(self) -> None:
        """Ensure all required indices exist with proper mappings."""
        try:
            await self.create_indices()
            await self.update_aliases()
        except Exception as e:
            logger.error(f"Failed to ensure indices: {e}")
            raise

    async def create_indices(self) -> None:
        """Create indices if they don't exist."""
        common_settings = {
            "settings": {
                "number_of_shards": 1,
                "number_of_replicas": 1,
                "analysis": {
                    "analyzer": {
                        "custom_analyzer": {
                            "type": "custom",
                            "tokenizer": "standard",
                            "filter": ["lowercase", "stop", "snowball"]
                        }
                    }
                }
            }
        }

        for index in ['commits', 'issues', 'pull_requests']:
            index_name = self.get_index_name(index)
            if not await self.client.indices.exists(index=index_name):
                try:
                    mapping_file = os.path.join(
                        os.path.dirname(__file__), 
                        'mappings', 
                        f'{index}_mapping.json'
                    )
                    with open(mapping_file, 'r') as f:
                        mapping = json.load(f)
                    
                    create_body = {
                        **common_settings,
                        "mappings": mapping["mappings"]
                    }
                    
                    await self.client.indices.create(
                        index=index_name,
                        **create_body
                    )
                    logger.info(f"Created index: {index_name}")
                except Exception as e:
                    logger.error(f"Failed to create index {index_name}: {e}")
                    raise

    async def update_aliases(self) -> None:
        """Update aliases for all indices."""
        try:
            actions = []
            for index in ['commits', 'issues', 'pull_requests']:
                index_name = self.get_index_name(index)
                alias_name = f"{self.settings.index_prefix}_{index}_alias"
                
                if await self.client.indices.exists(index=index_name):
                    actions.extend([
                        {"remove": {"index": "*", "alias": alias_name}},
                        {"add": {"index": index_name, "alias": alias_name}}
                    ])
            
            if actions:
                await self.client.indices.update_aliases(body={"actions": actions})
                logger.info("Updated index aliases")
        except Exception as e:
            logger.error(f"Failed to update aliases: {e}")
            raise

    async def reindex(self, source_index: str, target_index: str) -> None:
        """Reindex data from source to target index."""
        try:
            await self.client.reindex({
                "source": {"index": source_index},
                "dest": {"index": target_index}
            })
            logger.info(f"Reindexed from {source_index} to {target_index}")
        except Exception as e:
            logger.error(f"Failed to reindex from {source_index} to {target_index}: {e}")
            raise

    async def get_index_stats(self) -> Dict[str, Any]:
        """Get statistics for all indices."""
        try:
            indices = [self.get_index_name(name) for name in ['commits', 'issues', 'pull_requests']]
            stats = await self.client.indices.stats(index=indices)
            return stats
        except Exception as e:
            logger.error(f"Failed to get index stats: {e}")
            raise

    async def delete_indices(self):
        indices = [
            self.get_index_name(name) 
            for name in ['commits', 'issues', 'pull_requests']
        ]
        await self.client.indices.delete(index=indices, ignore=[404])
