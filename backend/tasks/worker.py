import os
from huey import RedisHuey

# Initialize Huey with Redis
huey = RedisHuey(
    name='githubxplainer',
    url=os.environ.get('REDIS_URL', 'redis://localhost:6379'),
    immediate=True,  # Set to True for testing/debugging
)
