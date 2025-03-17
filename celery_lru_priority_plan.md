# Celery LRU Priority Extension

## Overview

Create an extension library for Python Celery that provides fair task scheduling using LRU (Least Recently Used) prioritization.

## Core Components

1. **LRU-aware Task Decorator**
   - Extend Celery's `Task` class
   - Add `lru_delay(lru_key, *args, **kwargs)` method

2. **Task Backlog Storage**
   - Store pending tasks with their LRU keys
   - Use same backend as configured in Celery

3. **Prioritization Queue**
   - Dedicated queue for prioritization tasks
   - Separate from regular task queues

4. **Prioritization Worker**
   - Retrieves tasks from prioritization queue
   - Selects highest priority task from backlog
   - Executes selected task
   - Updates LRU tracking

5. **LRU Tracker**
   - Maintains history of when each LRU key was last used
   - Determines which client gets priority

## Implementation Plan

1. Create custom `LRUTask` class extending Celery's `Task`
2. Implement backlog storage using Celery's configured backend
3. Define prioritization task and worker logic
4. Build LRU tracking mechanism
5. Create simple API for application integration

## Usage Example

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