# Ranch Development Standards and Guidelines

## Project Commands

```bash
# Development environment
python -m venv venv
source venv/bin/activate
pip install -e ".[dev]"

# Testing
pytest                     # Run all tests
pytest -xvs                # Verbose test output
pytest --cov=ranch         # Run tests with coverage for ranch package
pytest --cov=ranch --cov-report=html  # Generate HTML coverage report
pytest tests/integration/  # Run only integration tests
pytest tests/test_lru_task.py  # Run specific test module

# Linting and formatting
flake8                     # Run linter
pylint ranch               # Run pylint on package
black .                    # Format code
isort .                    # Sort imports
pre-commit run --all-files # Run all pre-commit hooks

# Type checking
mypy .                     # Run type checker

# Celery
celery -A examples.docker_app.app.tasks worker --loglevel=info  # Run Celery worker for example app
celery -A examples.docker_app.app.tasks worker -Q priority_queue --loglevel=info  # Run worker for specific queue
celery -A examples.docker_app.app.tasks beat --loglevel=info  # Run Celery beat scheduler

# Building and publishing
python -m build            # Build package distributions
twine check dist/*         # Verify package quality
./scripts/publish.sh --test  # Publish to TestPyPI
./scripts/publish.sh       # Publish to PyPI
```

## Code Style

- Follow PEP 8 guidelines
- Maximum line length: 88 characters (Black default)
- Use type hints for all functions and methods
- Docstrings follow Google style format
- Import order: standard library → third-party → local modules
- Class organization: constants → class attributes → __init__ → public methods → private methods
- Always include return type annotations (`-> None`, `-> List[str]`, etc.)
- Prefer composition over inheritance when possible
- Use dataclasses for data containers

## Testing Standards

- Minimum test coverage: 80%
- Unit tests for all functions/methods
- Integration tests for worker tasks 
- Mocked brokers for testing task execution
- Test task revocation and failure cases
- Use parametrized tests for multiple input scenarios
- Create fixtures for common test setup
- Clearly name tests with pattern `test_<function>_<scenario>_<expected_result>`
- Test edge cases explicitly (empty inputs, max values, etc.)
- Add regression tests when fixing bugs

## Celery Best Practices

- Always specify task serializers explicitly (`json` recommended)
- Set reasonable timeouts for all tasks (default: 5 minutes)
- Use `task_always_eager` in testing environment
- Implement retry policies with exponential backoff
- Use task routing for workload distribution
- Monitor queue lengths and worker capacity
- Register tasks explicitly rather than relying on autodiscovery
- Set meaningful task names using `name` parameter
- Use immutable task signatures when appropriate
- Avoid storing large results in the result backend
- Consider using `ignore_result=True` for tasks that don't need result tracking

## Error Handling

- All tasks should handle exceptions gracefully
- Use `autoretry_for` for transient failures
- Log all task failures with appropriate context
- Define fallback behavior for critical tasks
- Implement dead letter queues for failed tasks
- Use Sentry or similar service for error tracking
- Don't use bare `except:` statements; catch specific exceptions
- Handle Redis connection failures gracefully
- Add monitoring for queue backlogs and stalled tasks

## Performance Considerations

- Use chunking for batch operations
- Implement rate limiting for resource-intensive tasks
- Configure worker concurrency based on CPU/memory constraints
- Optimize serialization method based on payload size
- Use result backends wisely - only when results needed
- Implement task priority using Ranch LRU prioritization
- Consider using the `--time-limit` and `--soft-time-limit` worker options
- Monitor worker memory usage to prevent OOM issues
- Use `prefetch_multiplier` to control message prefetching
- Consider Redis cluster for high-volume deployments

## Ranch-Specific Guidelines

- Always use `lru_task` decorator for tasks requiring fair scheduling
- Provide meaningful client IDs in `lru_delay()` calls
- Configure Redis persistence for production environments
- Monitor LRU queue lengths and processing times
- Consider custom backlog implementations for specialized use cases
- Use Redis for backlog storage in production
- Test with multiple concurrent clients to ensure fair scheduling
- Consider implementing custom prioritization strategies for specific requirements