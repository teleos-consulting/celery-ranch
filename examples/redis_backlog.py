"""
Advanced example showing how to use celery-ranch with Redis storage.

This demonstrates how to use Redis for persistent storage of the task backlog
and LRU tracking information.

To run this example:
1. Start a Redis server
2. Start a Celery worker:
   celery -A examples.redis_backlog worker -l info
3. In a separate terminal, run this script:
   python -m examples.redis_backlog
"""

import importlib.util
import random
import time

from celery import Celery

from celery_ranch import lru_task
from celery_ranch.utils.prioritize import configure

# Check if redis is installed
if importlib.util.find_spec("redis") is None:
    raise ImportError(
        "This example requires the redis package. "
        "Install it with: pip install celery-ranch[redis]"
    )

import redis

from celery_ranch.utils.persistence import RedisStorage

# Create a Celery application with Redis as broker and backend
app = Celery(
    "examples",
    broker="redis://localhost:6379/0",
    result_backend="redis://localhost:6379/0",
)

# Configure LRU priority with Redis storage
redis_client = redis.from_url("redis://localhost:6379/0")
redis_storage = RedisStorage(redis_client, prefix="my_app:celery_ranch:")
configure(app=app, storage=redis_storage)


# Define some LRU-aware tasks
@lru_task(app)
def process_data(data):
    """Simulate processing some data"""
    # Simulate work
    process_time = random.uniform(0.1, 0.5)
    time.sleep(process_time)

    print(f"Processing data: {data} (took {process_time:.2f}s)")
    return f"Processed: {data}"


@lru_task(app)
def analyze_data(data):
    """Simulate analyzing some data"""
    # Simulate work
    process_time = random.uniform(0.3, 0.8)
    time.sleep(process_time)

    print(f"Analyzing data: {data} (took {process_time:.2f}s)")
    return f"Analyzed: {data}"


def simulate_mixed_workload(client_count=3, tasks_per_client=5):
    """Simulate multiple clients submitting different types of tasks"""
    for i in range(tasks_per_client):
        # Each client submits processing and analysis tasks
        for client_id in range(client_count):
            # The LRU key is the client ID
            process_data.lru_delay(
                f"client_{client_id}", f"Dataset {i} from client {client_id}"
            )

            # Every other iteration, also submit an analysis task
            if i % 2 == 0:
                analyze_data.lru_delay(
                    f"client_{client_id}", f"Results {i} from client {client_id}"
                )

            # Simulate varying submission rates
            if client_id == 0:
                # Client 0 tries to submit tasks very quickly (high volume client)
                time.sleep(0.1)
            else:
                # Other clients submit less frequently
                time.sleep(random.uniform(0.5, 1.0))


if __name__ == "__main__":
    print("Simulating mixed workload with multiple clients...")
    simulate_mixed_workload()
    print("Tasks submitted. Check worker logs to see task execution.")
