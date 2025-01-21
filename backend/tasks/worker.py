import redis
from rq import Connection, Queue, Worker

from backend.config.redis_config import redis_conn
from backend.tasks import summary_tasks  # Import tasks to ensure they are registered

if __name__ == '__main__':
    with Connection(redis_conn):
        queues = [Queue('default'), Queue('high')]  # Define your queues
        worker = Worker(queues)
        worker.work()
