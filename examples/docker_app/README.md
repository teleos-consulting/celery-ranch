# Ranch Docker Example App

This example demonstrates using Ranch in a real-world application with Docker/Podman, Redis, and PostgreSQL.

## Overview

This application:

1. Uses Ranch for fair task scheduling with LRU prioritization
2. Stores data in PostgreSQL
3. Uses Redis for task queue and Ranch LRU tracking
4. Provides a simple web interface to submit and monitor jobs
5. Simulates client workloads with varying processing times

## Architecture

- **Web Interface**: Flask application for job submission and monitoring
- **Task Queue**: Celery with Redis as broker
- **Database**: PostgreSQL for storing client and job data
- **LRU Prioritization**: Ranch with Redis storage
- **Monitoring**: Flower for Celery task monitoring

## Running the Example

### Using Docker Compose

```bash
# Start all services
docker compose up -d

# View logs
docker compose logs -f

# Stop all services
docker compose down
```

### Using Podman

```bash
# Start all services with podman-compose
podman-compose up -d

# Or use podman directly
podman pod create --name ranch-example -p 8000:8000 -p 5555:5555 -p 6379:6379 -p 5432:5432
podman run -d --pod ranch-example --name redis redis:latest
podman run -d --pod ranch-example --name postgres -e POSTGRES_USER=ranch_user -e POSTGRES_PASSWORD=ranch_password -e POSTGRES_DB=ranch_db postgres:latest
podman build -t ranch-app .
podman run -d --pod ranch-example --name worker -e REDIS_URL=redis://localhost:6379/0 -e DATABASE_URL=postgresql://ranch_user:ranch_password@localhost:5432/ranch_db ranch-app celery -A app.tasks worker --loglevel=info
podman run -d --pod ranch-example --name web -e REDIS_URL=redis://localhost:6379/0 -e DATABASE_URL=postgresql://ranch_user:ranch_password@localhost:5432/ranch_db ranch-app python app/main.py
podman run -d --pod ranch-example --name flower -e CELERY_BROKER_URL=redis://localhost:6379/0 -e FLOWER_PORT=5555 mher/flower:latest
```

## How to Use

1. Access the web interface at http://localhost:8000
2. Create jobs for different clients using the UI
3. Generate random test jobs to see LRU prioritization in action
4. Watch how Ranch ensures fair distribution of tasks
5. Monitor Celery tasks at http://localhost:5555 (Flower)

## Key Files

- `docker-compose.yml`: Service configuration
- `Dockerfile`: Application container definition
- `app/tasks.py`: Ranch LRU task implementation
- `app/models.py`: Database models
- `app/routes.py`: Web API endpoints

## Exploring LRU Prioritization

To see Ranch's LRU prioritization in action:

1. Generate several jobs (10+) for a mix of clients
2. Observe the order of execution in the logs
3. Notice that clients take turns getting tasks executed, regardless of submission order
4. Try creating many jobs for a single client and see how Ranch prevents resource monopolization