# Ranch

[![Ranch CI](https://github.com/teleos-consulting/celery-ranch/actions/workflows/ci.yml/badge.svg)](https://github.com/teleos-consulting/celery-ranch/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/teleos-consulting/celery-ranch/branch/master/graph/badge.svg)](https://codecov.io/gh/teleos-consulting/celery-ranch)
[![PyPI version](https://badge.fury.io/py/ranch.svg)](https://badge.fury.io/py/ranch)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/release/python-380/)

A Python extension library for Celery that provides fair task scheduling using LRU (Least Recently Used) prioritization.

## Installation

```bash
pip install ranch
```

## Key Features

- Fair task distribution among multiple clients
- LRU-based prioritization of tasks
- Seamless integration with existing Celery applications
- No monopolization of resources by high-volume clients

## Usage

```python
from celery import Celery
from ranch import lru_task

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

## Development and Contribution

### Getting Started

1. Clone the repository:
   ```bash
   git clone https://github.com/teleos-consulting/celery-ranch.git
   cd celery-ranch
   ```

2. Create a virtual environment and install development dependencies:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -e ".[dev]"
   ```

### Running Tests

The project uses pytest for testing:

```bash
# Run all tests
pytest

# Run tests with coverage
pytest --cov=ranch

# Generate HTML coverage report
pytest --cov=ranch --cov-report=html
```

### Code Quality

We use several tools to ensure code quality:

```bash
# Run linters
flake8 ranch
pylint ranch

# Format code
black .
isort .

# Type checking
mypy .
```

### Contribution Guidelines

1. **Fork the repository** and create a feature branch from `master`.
2. **Write tests** for new features or bug fixes.
3. **Ensure all tests pass** and the code meets quality standards.
4. **Update documentation** if necessary.
5. **Submit a pull request** with a clear description of the changes.

#### Pull Request Process

1. Update the README.md or documentation with details of changes if appropriate.
2. Update the tests to reflect any changes to the functionality.
3. The PR should work for Python 3.8, 3.9, and 3.10.
4. PRs will be merged once they receive approval from maintainers.

### Code of Conduct

- Be respectful and inclusive in your communications.
- Focus on constructive feedback and collaboration.
- Help create a positive and supportive environment for all contributors.

## License

MIT
