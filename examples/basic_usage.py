"""
Basic example showing how to use ranch.

To run this example:
1. Start a Redis server
2. Start a Celery worker:
   celery -A examples.basic_usage worker -l info
3. In a separate terminal, run this script:
   python -m examples.basic_usage
"""

import random
import time

from celery import Celery

from ranch import lru_task

# Create a Celery application
app = Celery(
    "examples",
    broker="redis://localhost:6379/0",
    result_backend="redis://localhost:6379/0",
)


# Define some LRU-aware tasks
@lru_task(app)
def process_data(data):
    """Simulate processing some data"""
    # Simulate work
    process_time = random.uniform(0.1, 0.5)
    time.sleep(process_time)

    print(f"Processing data: {data} (took {process_time:.2f}s)")
    return f"Processed: {data}"


def simulate_clients(client_count=3, tasks_per_client=5):
    """Simulate multiple clients submitting tasks"""
    for i in range(tasks_per_client):
        # Each client submits a task - clients with more frequent requests
        # won't monopolize the worker
        for client_id in range(client_count):
            # The LRU key is the client ID
            process_data.lru_delay(
                f"client_{client_id}", f"Task {i} from client {client_id}"
            )

            # Simulate varying submission rates
            if client_id == 0:
                # Client 0 tries to submit tasks very quickly
                time.sleep(0.1)
            else:
                # Other clients submit less frequently
                time.sleep(random.uniform(0.5, 1.0))


if __name__ == "__main__":
    print("Simulating multiple clients submitting tasks...")
    simulate_clients()
    print("Tasks submitted. Check worker logs to see task execution.")
