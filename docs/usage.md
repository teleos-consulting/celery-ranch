# Celery LRU Priority Usage Guide

## Introduction

Celery LRU Priority is a Python extension library for Celery that provides fair task scheduling using LRU (Least Recently Used) prioritization. It prevents high-volume clients from monopolizing task queues.

## Installation

Install the package using pip:

```bash
pip install celery-lru-priority
```

## Basic Usage

### Creating LRU-aware Tasks

Use the `lru_task` decorator instead of Celery's standard `@app.task` decorator:

```python
from celery import Celery
from celery_lru_priority import lru_task

app = Celery('tasks')

@lru_task(app)
def process_data(data):
    # Process data
    return result
```

### Submitting Tasks with LRU Prioritization

To submit a task with LRU prioritization, use the `lru_delay` method instead of the standard `delay`:

```python
# Regular Celery task execution
# result = process_data.delay(data_to_process)

# LRU prioritized task execution
result = process_data.lru_delay("client_id", data_to_process)
```

The first argument to `lru_delay` is the LRU key, which identifies the client or process submitting the task. Subsequent arguments are passed to the task function as usual.

## How It Works

1. When you call `lru_delay`, the task is stored in a backlog rather than being sent directly to a queue
2. A prioritization task is placed in a special queue
3. When a worker processes the prioritization task, it:
   - Retrieves all pending LRU keys from the backlog
   - Selects the least recently used key
   - Retrieves and executes a task from that client
   - Updates the LRU timestamp for that client

This ensures that clients who submit tasks less frequently will still get fair access to resources, even when high-volume clients are active.

## Advanced Configuration

### Using Redis for Persistent Storage

By default, the library uses in-memory storage for the task backlog and LRU tracking. For production use, it's recommended to use Redis:

```python
import redis
from celery import Celery
from celery_lru_priority import lru_task
from celery_lru_priority.utils.persistence import RedisStorage
from celery_lru_priority.utils.prioritize import configure

app = Celery('tasks')

# Configure with Redis storage
redis_client = redis.from_url('redis://localhost:6379/0')
redis_storage = RedisStorage(redis_client, prefix="my_app:lru_priority:")
configure(app=app, storage=redis_storage)

@lru_task(app)
def process_data(data):
    # Process data
    return result
```

### Custom Task Base Class

You can customize the task base class:

```python
from celery_lru_priority import lru_task
from celery_lru_priority.task import LRUTask

class MyCustomTask(LRUTask):
    # Custom behavior
    pass

@lru_task(app, base=MyCustomTask)
def process_data(data):
    # Process data
    return result
```

## Best Practices

### Choosing LRU Keys

LRU keys should identify the client, user, or process submitting tasks:

- User IDs for user-specific tasks
- Client application IDs for service-to-service communication
- Department or tenant IDs for multi-tenant systems

### Worker Configuration

For optimal LRU scheduling:

1. Dedicate workers to processing prioritization tasks:
   ```bash
   celery -A myapp worker -Q celery_lru_priority -l info
   ```

2. Configure priority queue concurrency appropriately:
   ```python
   app.conf.task_routes = {
       'celery_lru_priority.prioritize_task': {'queue': 'celery_lru_priority'}
   }
   ```

### Monitoring

Monitor the backlog size to ensure tasks aren't accumulating:

```python
from celery_lru_priority.utils.prioritize import _task_backlog

# Get all LRU keys in the backlog
lru_keys = _task_backlog.get_all_lru_keys()

# Count tasks for each key
for key in lru_keys:
    tasks = _task_backlog.get_tasks_by_lru_key(key)
    print(f"Client {key}: {len(tasks)} pending tasks")
```

## Limitations

- Task results are still handled by Celery's standard result backend
- Tasks in the backlog are lost if the process or Redis server restarts (unless persistence is configured)
- Not suitable for tasks that must be executed in a specific order

## Troubleshooting

### Tasks Not Being Executed

- Ensure prioritization workers are running
- Check that the Redis server is accessible (if using Redis storage)
- Verify that the LRU key is being provided correctly

### High Latency

- Increase the number of prioritization workers
- Split high-volume clients into multiple LRU keys
- Consider adding task expiration to the backlog