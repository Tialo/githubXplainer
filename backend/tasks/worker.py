from backend.config.huey_config import huey

# Import tasks to ensure they are registered
from backend.tasks import summary_tasks

if __name__ == '__main__':
    from huey.consumer import Consumer
    consumer = Consumer(huey, workers=1, max_delay=10)
    consumer.run()
