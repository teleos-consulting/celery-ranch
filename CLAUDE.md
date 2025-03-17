# Python & Celery Development Standards

## Project Commands

```bash
# Development environment
python -m venv venv
source venv/bin/activate
pip install -e ".[dev]"

# Testing
pytest                     # Run all tests
pytest -xvs                # Verbose test output
pytest --cov=.             # Run tests with coverage
pytest --cov=. --cov-report=html  # Generate HTML coverage report

# Linting
flake8                     # Run linter
black .                    # Format code
isort .                    # Sort imports

# Type checking
mypy .                     # Run type checker

# Celery
celery -A myapp.celery worker --loglevel=info  # Run Celery worker
celery -A myapp.celery worker -Q priority_queue --loglevel=info  # Run worker for specific queue
celery -A myapp.celery beat --loglevel=info  # Run Celery beat scheduler
```

## Code Style

- Follow PEP 8 guidelines
- Maximum line length: 88 characters (Black default)
- Use type hints for all functions and methods
- Docstrings follow Google style format

## Testing Standards

- Minimum test coverage: 80%
- Unit tests for all functions/methods
- Integration tests for worker tasks
- Mocked brokers for testing task execution
- Test task revocation and failure cases

## Celery Best Practices

- Always specify task serializers explicitly
- Set reasonable timeouts for all tasks
- Use `task_always_eager` in testing environment
- Implement retry policies with exponential backoff
- Use task routing for workload distribution
- Monitor queue lengths and worker capacity

## Error Handling

- All tasks should handle exceptions gracefully
- Use `autoretry_for` for transient failures
- Log all task failures with appropriate context
- Define fallback behavior for critical tasks

## Performance Considerations

- Use chunking for batch operations
- Implement rate limiting for resource-intensive tasks
- Configure worker concurrency based on CPU/memory constraints
- Optimize serialization method based on payload size
- Use result backends wisely - only when results needed