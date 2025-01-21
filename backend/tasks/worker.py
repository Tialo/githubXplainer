import os
from huey import RedisHuey

# Initialize Huey with Redis
huey = RedisHuey(
    name='githubxplainer',
    url=os.environ.get('REDIS_URL', 'redis://localhost:6379'),
    immediate=False,
    results=True,
    # Store locks for up to 1 hour
    lock_timeout=3600,
    max_workers=1  # Ensure single worker
)

if __name__ == '__main__':
    from huey.consumer import Consumer
    consumer = Consumer(huey, workers=1, max_delay=10)
    consumer.run()
