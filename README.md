# Celery LRU Priority

A Python extension library for Celery that provides fair task scheduling using LRU (Least Recently Used) prioritization.

## Installation

```bash
pip install celery-lru-priority
```

## Key Features

- Fair task distribution among multiple clients
- LRU-based prioritization of tasks
- Seamless integration with existing Celery applications
- No monopolization of resources by high-volume clients

## Usage

```python
from celery import Celery
from celery_lru_priority import lru_task

app = Celery('tasks')

@lru_task(app)
def process_data(data):
    # Process data
    return result

# Using LRU prioritization - "client_id" is the LRU key
result = process_data.lru_delay("client_id", data_to_process)
```

## How It Works

The library works by:
1. Intercepting task calls via the `lru_delay()` method
2. Placing the original task in a backlog
3. Creating a prioritization task in a dedicated queue
4. Using a worker to select the highest priority task based on LRU history
5. Executing the selected task and updating the LRU tracking

## License

MIT
