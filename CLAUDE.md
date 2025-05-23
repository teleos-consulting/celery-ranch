# Celery Ranch Development Standards and Guidelines

## GitHub Workflow

Before starting work on any feature or bug fix:

1. Check for existing remote branches and GitHub issues:
   ```bash
   # List all remote branches
   git fetch --all
   git branch -r

   # Fetch latest GitHub issues and their status
   gh issue list --limit 50
   
   # Get detailed info about a specific issue
   gh issue view ISSUE_NUMBER
   ```

2. Check if a branch already exists for your task:
   ```bash
   # Search for branches containing keywords
   git branch -r | grep -i "keyword"
   
   # Check if branch exists on remote
   git ls-remote --heads origin branch-name
   ```

3. Check related pull requests:
   ```bash
   # List open pull requests
   gh pr list
   
   # Check if PRs exist for an issue
   gh pr list --search "issue:#ISSUE_NUMBER"
   ```

4. Create a new branch with a descriptive name if needed:
   ```bash
   git checkout -b feature/issue-number-short-description
   ```

## Local Development Workflow

To minimize GitHub Actions time consumption and avoid failed CI builds, follow this local workflow before pushing changes:

1. Run pre-commit hooks on all modified files:
   ```bash
   pre-commit run --files $(git diff --name-only)
   ```

2. Run type checking and linting focused on the main package:
   ```bash
   mypy .
   flake8 celery_ranch
   pylint celery_ranch
   ```

3. Run tests with coverage to ensure the required 80% threshold is met:
   ```bash
   pytest --cov=celery_ranch --cov-report=term-missing
   ```

4. If tests fail, troubleshoot by running specific test files with detailed output:
   ```bash
   pytest tests/test_failing_file.py -xvs
   ```

5. Before submitting a PR, make a final verification:
   ```bash
   # Verify all tests pass
   pytest

   # Check coverage meets requirements (80% or higher)
   pytest --cov=celery_ranch --cov-report=term-missing

   # Run linting on main package code
   flake8 celery_ranch
   pylint celery_ranch
   
   # Verify type checking
   mypy .
   ```

6. For significant changes, check GitHub Actions locally with `act`:
   ```bash
   act -j unit-tests
   ```

This workflow catches most issues locally before triggering CI workflows, saving time and resources.

## Project Commands

```bash
# Development environment
python -m venv venv
source venv/bin/activate
pip install -e ".[dev]"

# Testing
pytest                                # Run all tests
pytest -xvs                           # Verbose test output
pytest tests/test_file.py -xvs        # Run one test file with verbose output
pytest --cov=celery_ranch                    # Run tests with coverage for celery_ranch package
pytest --cov=celery_ranch --cov-report=term-missing  # Coverage with report of missing lines
pytest --cov=celery_ranch --cov-report=html  # Generate HTML coverage report
pytest tests/integration/             # Run only integration tests
pytest tests/test_lru_task.py         # Run specific test module
pytest -k "test_name_pattern"         # Run tests matching a pattern

# Linting and formatting
flake8 celery_ranch               # Run flake8 linter on main package only (faster)
flake8                     # Run flake8 on whole project
pylint celery_ranch               # Run pylint on package only (more focused results)
black celery_ranch                # Format main package code
black .                    # Format all code
isort celery_ranch                # Sort imports in main package
isort .                    # Sort imports in all files
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

- Minimum test coverage: 80% (package requirement enforced by CI)
- Unit tests for all functions/methods
- Integration tests for worker tasks (Redis required for some tests)
- Mocked brokers for testing task execution (avoids Redis dependency for most tests)
- Test task revocation and failure cases
- Use parametrized tests for multiple input scenarios
- Create fixtures for common test setup
- Clearly name tests with pattern `test_<function>_<scenario>_<expected_result>`
- Test edge cases explicitly (empty inputs, max values, etc.)
- Add regression tests when fixing bugs

### Test Best Practices

- Focus on testing functionality, not implementation details
- Never reference specific line numbers in test comments as code changes frequently
- Write test comments that describe the functionality or edge case being tested
- Tests should be understandable even if the implementation changes
- Focus on behaviors and boundary conditions rather than code paths
- Group related test cases together for better organization
- Test behavior, not code coverage - if specific code paths are hard to test, consider refactoring
- Each test should assert one conceptual behavior for easier debugging
- Tests that explicitly track test coverage should be avoided; coverage is a byproduct of good tests

### Test Mocking Best Practices

- Mock time-dependent functions (use `patch('time.time')` with fixed return values)
- Use appropriate mocking for Redis operations (`patch.object(storage, '_redis')`)
- Mock logger to prevent excessive output during tests (`patch('module.logger')`)
- For storage testing, mock the storage interface rather than real Redis connections
- Use side_effect on mocks to create dynamic mock behavior for complex flows
- When testing error handling, mock exceptions with `side_effect = Exception("message")`

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
- Implement task priority using Celery Ranch LRU prioritization
- Consider using the `--time-limit` and `--soft-time-limit` worker options
- Monitor worker memory usage to prevent OOM issues
- Use `prefetch_multiplier` to control message prefetching
- Consider Redis cluster for high-volume deployments

## Celery Ranch-Specific Guidelines

- Always use `lru_task` decorator for tasks requiring fair scheduling
- Provide meaningful client IDs in `lru_delay()` calls
- Configure Redis persistence for production environments
- Monitor LRU queue lengths and processing times
- Consider custom backlog implementations for specialized use cases
- Use Redis for backlog storage in production
- Test with multiple concurrent clients to ensure fair scheduling
- Consider implementing custom prioritization strategies for specific requirements

## Pull Request Preparation Checklist

Before creating a pull request, run this comprehensive checklist to ensure code quality:

```bash
# 1. Run linting across ALL files (not just modified ones)
flake8

# 2. Run type checking across the entire codebase
mypy .

# 3. Run test suite with coverage
pytest --cov=celery_ranch --cov-report=term-missing

# 4. Verify import formatting
isort --check .

# 5. Check code formatting
black --check .

# 6. Apply any required formatting fixes
isort .
black .

# 7. Run pylint on key packages
pylint celery_ranch
pylint ranch

# 8. Final verification
flake8
```

Always run the full linting and type checking before pushing code for review.

## Feature Branch and Issue Management

- Always check issue details completely before starting work:
  ```bash
  # Get full details about the issue
  gh issue view ISSUE_NUMBER --comments
  ```

- When selecting a branch name, use a consistent prefix pattern:
  - `feature/issue-XX-short-name` for new features
  - `bugfix/issue-XX-short-name` for bug fixes 
  - `docs/issue-XX-short-name` for documentation updates
  - `refactor/issue-XX-short-name` for code refactoring

- Check if work already exists before starting:
  ```bash
  # Check if anyone is working on the issue
  gh issue view ISSUE_NUMBER --json assignees
  
  # Check for related branches
  git fetch --all
  git branch -r | grep -i "issue-XX"
  ```

- Always pull latest changes before starting work:
  ```bash
  git checkout master
  git pull
  git checkout -b feature/issue-XX-short-name
  ```

- When returning to a branch after time away:
  ```bash
  # Update remote branches and rebase your work
  git fetch --all
  git checkout your-branch-name
  git rebase origin/master
  ```

- Check if anyone else has modified your branch:
  ```bash
  git fetch
  git log HEAD..origin/your-branch-name
  ```

- Regularly sync with the main branch to avoid merge conflicts:
  ```bash
  git checkout your-branch-name
  git rebase origin/master
  ```

## CI/CD Pipeline Optimization

- Use conditional workflows in GitHub Actions to run only relevant jobs
- Enable caching for dependencies in CI workflows:
  ```yaml
  - uses: actions/cache@v3
    with:
      path: ~/.cache/pip
      key: ${{ runner.os }}-pip-${{ hashFiles('**/requirements.txt') }}
  ```
- Parallelize tests by splitting them into different jobs
- Run linting and type checking as separate jobs that can fail fast
- Use matrix builds to test across multiple Python versions efficiently
- Consider using GitHub Actions' `paths` filters to skip workflows for non-code changes:
  ```yaml
  on:
    push:
      paths:
        - '**.py'
        - 'requirements.txt'
        - 'setup.py'
        - 'pyproject.toml'
  ```
- For documentation-only changes, skip test workflows
- Set up local CI checks with pre-commit hooks before pushing changes