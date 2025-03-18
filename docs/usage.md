# Celery Ranch Usage Guide

## Introduction

Celery Ranch is a Python extension library for Celery that provides fair task scheduling using LRU (Least Recently Used) prioritization. It prevents high-volume bulk processes from monopolizing task queues, ensuring fair access for all task sources - whether they're batch jobs, interactive user requests, scheduled operations, or critical on-demand processes.

## Installation

Install the package using pip:

```bash
pip install celery-ranch
```

For production environments with Redis support (recommended):

```bash
pip install celery-ranch[redis]
```

## Basic Usage

### Creating LRU-aware Tasks

Use the `lru_task` decorator instead of Celery's standard `@app.task` decorator:

```python
from celery import Celery
from celery_ranch import lru_task

app = Celery('tasks')

@lru_task(app)
def process_data(data):
    # Process data
    return result
```

### Submitting Tasks with LRU Prioritization

To submit a task with LRU prioritization, use the `lru_delay` method instead of the standard `delay`:

```python
# Regular Celery task execution (no fair scheduling)
# result = process_data.delay(data_to_process)

# LRU prioritized task execution with process identifier
result = process_data.lru_delay("batch_job_id", data_to_process)
```

The first argument to `lru_delay` is the LRU key, which identifies the process or source submitting the task. It could be a batch job ID, user ID, department code, service name, or any other identifier that distinguishes different task sources. Subsequent arguments are passed to the task function as usual.

## How Fair Scheduling Works

1. When you call `lru_delay`, the task is stored in a backlog rather than being sent directly to a queue
2. A lightweight prioritization task is placed in a special queue
3. When a worker processes the prioritization task, it:
   - Retrieves all pending process identifiers (LRU keys) from the backlog
   - Selects the least recently served process identifier
   - Retrieves and executes a task from that process's queue
   - Updates the LRU timestamp for that process

This ensures that all processes get fair access to resources regardless of submission frequency. A high-volume batch process submitting thousands of tasks will not starve out interactive user requests or other critical operations.

## Advanced Configuration

### Using Redis for Persistent Storage

By default, the library uses in-memory storage for the task backlog and LRU tracking. For production use, it's strongly recommended to use Redis:

```python
import redis
from celery import Celery
from celery_ranch import lru_task
from celery_ranch.utils.persistence import RedisStorage
from celery_ranch.utils.prioritize import configure

app = Celery('tasks')

# Configure with Redis storage
redis_client = redis.from_url('redis://localhost:6379/0')
redis_storage = RedisStorage(redis_client, prefix="my_app:celery_ranch:")
configure(app=app, storage=redis_storage)

@lru_task(app)
def process_data(data):
    # Process data
    return result
```

### Comprehensive Configuration

For production deployments, you can use a more comprehensive configuration:

```python
from celery import Celery
from celery_ranch import SerializerType, lru_task

app = Celery('tasks', broker='redis://localhost:6379/0')

# Configure Celery Ranch
app.conf.celery_ranch = {
    "redis_prefix": "myapp:",                # Namespace for Redis keys
    "redis_serializer": SerializerType.JSON, # More human-readable in Redis
    "redis_key_ttl": 3600,                   # Default 1-hour expiry for keys
    "redis_max_retries": 3,                  # Connection retry attempts
    "redis_use_ssl": True,                   # For secure Redis connections
    "metrics_enabled": True,                 # Enable built-in metrics
}

@lru_task(app)
def process_data(data):
    # Process data
    return result
```

### Custom Task Base Class

You can customize the task base class for specialized behavior:

```python
from celery_ranch import lru_task
from celery_ranch.task import LRUTask

class MyCustomTask(LRUTask):
    # Custom behavior
    def on_success(self, retval, task_id, args, kwargs):
        # Custom success handling
        super().on_success(retval, task_id, args, kwargs)
        
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        # Custom failure handling
        super().on_failure(exc, task_id, args, kwargs, einfo)

@lru_task(app, base=MyCustomTask)
def process_data(data):
    # Process data
    return result
```

## Best Practices

### Choosing LRU Keys (Process Identifiers)

LRU keys should identify the source or category of the task:

- **Batch Jobs**: Use job IDs or job type identifiers (`nightly_batch_123`, `report_generation`)
- **User Operations**: User IDs or session IDs for user-specific task sources
- **Service Categories**: Service or subsystem names (`payment_processor`, `recommendation_engine`)
- **Department/Team**: Team identifiers for organizational task sources (`marketing`, `finance`)
- **Priority Levels**: Categories based on importance (`critical`, `normal`, `background`)

### Worker Configuration

For optimal fair scheduling:

1. Dedicate workers to processing prioritization tasks:
   ```bash
   celery -A myapp worker -Q celery_ranch -l info
   ```

2. Configure priority queue routing in your Celery application:
   ```python
   app.conf.task_routes = {
       'celery_ranch.prioritize_task': {'queue': 'celery_ranch'}
   }
   ```

3. For high-throughput systems, adjust worker concurrency:
   ```bash
   celery -A myapp worker -Q celery_ranch -l info --concurrency=4
   ```

### Performance Optimization

- **Task Expiry**: Set appropriate expiry times for tasks that become irrelevant after a certain period
- **Batching**: Group related tasks under the same LRU key when they logically belong together
- **Priority Segmentation**: Use different priority weights for different categories of operations
- **Redis Connection Pooling**: Ensure your Redis client is configured to use connection pooling

### Monitoring

Monitor the backlog size to ensure efficient task processing:

```python
from celery_ranch.utils.prioritize import _task_backlog

# Get all process identifiers (LRU keys) in the backlog
process_ids = _task_backlog.get_all_lru_keys()

# Count pending tasks for each process
for process_id in process_ids:
    tasks = _task_backlog.get_tasks_by_lru_key(process_id)
    print(f"Process {process_id}: {len(tasks)} pending tasks")
    
# Get overall system status
from celery_ranch.utils.lru_tracker import _lru_tracker
last_used = _lru_tracker.get_last_used_times()
print(f"Total processes tracked: {len(last_used)}")
```

## Limitations

- Task results are still handled by Celery's standard result backend
- Without Redis persistence, tasks in the backlog are lost if the process or Redis server restarts
- Not designed for tasks that must be executed in a specific sequence within a process
- Additional latency for task execution compared to direct Celery task submission

## Troubleshooting

### Tasks Not Being Executed

- Ensure prioritization workers are running with the correct queue (`celery_ranch`)
- Check Redis connectivity if using Redis storage
- Verify LRU keys (process identifiers) are being provided correctly
- Check for orphaned tasks with `get_all_lru_keys()` and `get_tasks_by_lru_key()`

### High Latency or Backlog Growth

- Increase prioritization worker count or concurrency
- Segment high-volume processes into multiple LRU keys
- Add task expiry to prevent stale task accumulation
- Use weighted priorities to optimize critical task processing

### Memory Usage Concerns

- Use Redis storage for production deployments
- Configure appropriate key TTL values to prevent indefinite key growth
- Monitor Redis memory usage in high-volume environments

## Code Coverage and Quality

Celery Ranch maintains high test coverage to ensure reliability:

```bash
# Generate HTML coverage report
pytest --cov=celery_ranch --cov-report=html

# Generate XML coverage report for Codecov
pytest --cov=celery_ranch --cov-report=xml
```

View the latest coverage reports on [Codecov](https://codecov.io/gh/teleos-consulting/celery-ranch).