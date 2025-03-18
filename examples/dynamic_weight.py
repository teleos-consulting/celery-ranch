"""
Example demonstrating custom dynamic weight functions.

This example shows how to:
1. Create a custom dynamic weight function for prioritization
2. Store custom data for each client
3. Use the custom data in the weight function to determine priority

The example simulates a bidding system where clients with higher bids get
higher priority.

To run this example:
1. Start a Redis server
2. Start a Celery worker:
   celery -A examples.dynamic_weight worker -l info
3. In a separate terminal, run this script:
   python -m examples.dynamic_weight
"""

import random
import time
from datetime import datetime

from celery import Celery

from celery_ranch import SerializerType, lru_task
from celery_ranch.utils.lru_tracker import LRUKeyMetadata

# Create a Celery application with Redis broker
app = Celery(
    "examples",
    broker="redis://localhost:6379/0",
    result_backend="redis://localhost:6379/0",
)

# Configure Celery Ranch with JSON serializer
app.conf.celery_ranch = {
    "redis_prefix": "celery_ranch_dynamic_example:",
    "redis_serializer": SerializerType.JSON,
    "redis_key_ttl": 3600,  # 1-hour expiry for keys
}


# Define a custom weight function that uses bid values
def bid_based_priority(lru_key: str, metadata: LRUKeyMetadata) -> float:
    """
    Calculate priority based on bid value in custom data.

    Lower weight = higher priority, so we return 1.0 / bid_value.
    For example, a bid of 10 would result in a priority weight of 0.1.
    """
    # Default weight
    if not metadata.custom_data or "bid" not in metadata.custom_data:
        return 1.0

    # Get the bid value
    bid = metadata.custom_data.get("bid", 1.0)

    # Ensure bid is positive
    if bid <= 0:
        return 1.0

    # Return inverted bid (lower weight = higher priority)
    return 1.0 / bid


# Define a task with custom weight function
@lru_task(app, weight_function=bid_based_priority)
def process_data(client_name, data_size, processing_type):
    """Simulate processing data with different execution times."""
    # Simulate work with varying processing times
    process_time = data_size * random.uniform(0.1, 0.5)
    time.sleep(process_time)

    timestamp = datetime.now().strftime("%H:%M:%S")
    print(
        f"[{timestamp}] Processing {processing_type} data for {client_name}: "
        f"{data_size}MB (took {process_time:.2f}s)"
    )

    return {
        "client": client_name,
        "size": data_size,
        "type": processing_type,
        "time": process_time,
    }


def simulate_bid_based_priority():
    """Simulate clients bidding for priority."""
    # Client definitions with different bid values
    clients = {
        "high_bidder": 10.0,     # Highest bid, should get highest priority
        "medium_bidder": 5.0,    # Medium bid
        "low_bidder": 1.0,       # Low bid, should get lowest priority
    }

    # Set bids for each client
    for client_name, bid in clients.items():
        # Store the bid as custom data
        process_data.set_custom_data(client_name, "bid", bid)
        print(f"Set bid for {client_name}: {bid}")

    # Submit tasks for each client
    for i in range(5):  # 5 tasks per client
        for client_name in clients:
            # Determine data size (1-10 MB)
            data_size = random.uniform(1, 10)

            # Submit task
            process_data.lru_delay(
                client_name,  # LRU key
                client_name,  # Client name (arg)
                data_size,    # Data size (arg)
                "bidding",    # Processing type (arg)
                tags={"type": "bid_example"},
            )

            # Short delay between submissions
            time.sleep(0.2)

    # Show client metadata
    print("\nClient metadata:")
    for client_name in clients:
        metadata = process_data.get_client_metadata(client_name)
        print(
            f"{client_name}: bid={metadata['custom_data']['bid']}, "
            f"pending_tasks={metadata['pending_tasks']}"
        )

    # Get system status
    status = process_data.get_system_status()
    print(f"\nSystem status: {status}")


if __name__ == "__main__":
    print("Simulating bid-based prioritization...")
    print("Watch how high bidders get processed more frequently.")
    print("=" * 60)
    simulate_bid_based_priority()
    print("=" * 60)
    print("Tasks submitted. Check worker logs to see execution order.")
    print(
        "Notice how high_bidder tasks get executed more frequently "
        "than low_bidder tasks."
    )
