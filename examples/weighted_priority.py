"""
Example demonstrating weighted LRU prioritization.

This example shows how to:
1. Set different priority weights for different clients
2. Use task expiry to automatically discard stale tasks
3. Use client tags for organization and filtering

To run this example:
1. Start a Redis server
2. Start a Celery worker:
   celery -A examples.weighted_priority worker -l info
3. In a separate terminal, run this script:
   python -m examples.weighted_priority
"""

import random
import time
from datetime import datetime

from celery import Celery

from ranch import lru_task, SerializerType

# Create a Celery application with Redis broker
app = Celery(
    "examples",
    broker="redis://localhost:6379/0",
    result_backend="redis://localhost:6379/0",
)

# Configure Ranch with JSON serializer and key expiry
app.conf.ranch = {
    "redis_prefix": "ranch_example:",
    "redis_serializer": SerializerType.JSON,  # More human-readable in Redis
    "redis_key_ttl": 3600,  # Default 1-hour expiry for keys
    "redis_max_retries": 3,
    "metrics_enabled": True
}


# Define an LRU-aware task
@lru_task(app)
def process_data(client_name, data_size, processing_type):
    """Simulate processing data with different execution times."""
    # Simulate work with varying processing times
    process_time = data_size * random.uniform(0.1, 0.5)
    time.sleep(process_time)
    
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] Processing {processing_type} data for {client_name}: "
          f"{data_size}MB (took {process_time:.2f}s)")
    
    return {
        "client": client_name,
        "size": data_size,
        "type": processing_type,
        "time": process_time
    }


def simulate_weighted_priority():
    """Simulate clients with different priority weights."""
    # Client definitions with different weights
    clients = {
        "high_priority": 0.5,    # 2x priority
        "normal_priority": 1.0,  # normal priority
        "low_priority": 2.0,     # 0.5x priority
    }
    
    # Submit tasks for each client
    for i in range(5):  # 5 tasks per client
        for client_name, weight in clients.items():
            # Set priority weight on first run
            if i == 0:
                process_data.set_priority_weight(client_name, weight)
                # Add tags for organization
                process_data.add_tag(client_name, "type", client_name.split("_")[0])
                
            # Determine data size (1-10 MB)
            data_size = random.uniform(1, 10)
            
            # Submit task with priority weight
            process_data.lru_delay(
                client_name,                   # LRU key
                client_name,                   # Client name (arg)
                data_size,                     # Data size (arg)
                "sensitive" if i % 2 == 0 else "normal",  # Processing type (arg)
                priority_weight=weight,        # Priority weight
                tags={"iteration": str(i)},    # Add metadata tags
                expiry=300                     # Tasks expire after 5 minutes
            )
            
            # Short delay between submissions
            time.sleep(0.2)
    
    # Show client status
    print("\nClient status:")
    for client_name in clients:
        metadata = process_data.get_client_metadata(client_name)
        print(f"{client_name}: weight={metadata['weight']}, "
              f"pending_tasks={metadata['pending_tasks']}")
    
    # Get system status
    status = process_data.get_system_status()
    print(f"\nSystem status: {status}")
    
    # Find clients by tag
    high_clients = process_data.get_tagged_clients("type", "high")
    print(f"\nHigh priority clients: {high_clients}")
            

if __name__ == "__main__":
    print("Simulating weighted priority task execution...")
    print("Watch how high priority clients get serviced more frequently.")
    print("=" * 60)
    simulate_weighted_priority()
    print("=" * 60)
    print("Tasks submitted. Check worker logs to see execution order.")
    print("Notice how high_priority tasks get executed more frequently than low_priority tasks.")