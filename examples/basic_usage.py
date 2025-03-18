"""
Basic example showing how to use celery-ranch for fair task scheduling.

This example demonstrates how Celery Ranch prevents high-volume bulk processes 
from monopolizing your task queue, ensuring all processes get fair access to resources.

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

from celery_ranch import lru_task

# Create a Celery application
app = Celery(
    "examples",
    broker="redis://localhost:6379/0",
    result_backend="redis://localhost:6379/0",
)


# Define an LRU-aware task
@lru_task(app)
def process_data(data):
    """Simulate processing some data"""
    # Simulate work
    process_time = random.uniform(0.1, 0.5)
    time.sleep(process_time)

    print(f"Processing data: {data} (took {process_time:.2f}s)")
    return f"Processed: {data}"


def simulate_competing_processes():
    """
    Simulate different types of processes competing for worker resources:
    - bulk_batch: High-volume batch job that tries to submit many tasks quickly
    - user_request: Interactive user requests that happen less frequently
    - background_job: Regular background jobs that run periodically
    """
    # Define our different process types
    processes = {
        "bulk_batch": {"count": 15, "delay": 0.1},         # Submits tasks rapidly
        "user_request": {"count": 5, "delay": 0.8},        # Less frequent
        "background_job": {"count": 8, "delay": 0.5}       # Medium frequency
    }

    # Submit tasks in a realistic pattern (interleaved)
    for i in range(max(p["count"] for p in processes.values())):
        for process_type, config in processes.items():
            # Only submit if this process still has tasks in this round
            if i < config["count"]:
                # Use the process type as the LRU key
                process_data.lru_delay(
                    process_type, 
                    f"Task {i} from {process_type}"
                )
                
                # Simulate different submission rates
                time.sleep(config["delay"])
                
                # Without Celery Ranch, the bulk_batch would monopolize 
                # the worker due to its rapid submission rate


if __name__ == "__main__":
    print("Simulating competing processes submitting tasks...")
    print("Notice how Celery Ranch ensures fair scheduling despite different submission rates.")
    print("-" * 70)
    simulate_competing_processes()
    print("-" * 70)
    print("Tasks submitted. Check worker logs to see how tasks are fairly distributed.")
    print("Without Celery Ranch, bulk_batch tasks would dominate, starving other processes.")
