# Celery Ranch

[![Celery Ranch CI](https://github.com/teleos-consulting/celery-ranch/actions/workflows/ci.yml/badge.svg)](https://github.com/teleos-consulting/celery-ranch/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/teleos-consulting/celery-ranch/branch/main/graph/badge.svg?token=GNXKAEISFB)](https://codecov.io/gh/teleos-consulting/celery-ranch)
[![PyPI version](https://badge.fury.io/py/celery-ranch.svg)](https://badge.fury.io/py/celery-ranch)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/release/python-380/)
[![Celery 5.3.4+](https://img.shields.io/badge/celery-5.3.4+-green.svg)](https://docs.celeryproject.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Sponsor on GitHub](https://img.shields.io/badge/sponsor-on%20github-blue?logo=github)](https://github.com/sponsors/teleos-consulting)

A Python extension library for Celery that provides fair task scheduling using LRU (Least Recently Used) prioritization. Designed to prevent high-volume bulk processes from monopolizing resources while ensuring fair access for all task sources - whether they're from bulk operations, user interactions, scheduled jobs, or critical on-demand processes.

## Installation

```bash
# Install from PyPI (currently unavailable)
pip install celery-ranch

# Install directly from GitHub
pip install git+https://github.com/teleos-consulting/celery-ranch.git

# Install a specific version from GitHub
pip install git+https://github.com/teleos-consulting/celery-ranch.git@v0.1.0
```

For production use with Redis storage:

```bash
# From PyPI (currently unavailable)
pip install celery-ranch[redis]

# From GitHub
pip install "git+https://github.com/teleos-consulting/celery-ranch.git#egg=celery-ranch[redis]"
```

## Key Features

- **Fair Resource Distribution**: Ensures equitable task execution across different processes
- **LRU-based Prioritization**: Automatically prioritizes less recently served task sources
- **Weighted Priority System**: Assign different priority levels to various process types
- **Custom Weight Functions**: Define advanced prioritization logic based on your specific needs
- **Task Expiry Management**: Prevent stale tasks from consuming valuable resources
- **Process Tagging**: Organize and filter task sources with customizable tags
- **Seamless Celery Integration**: Works with your existing Celery applications without major changes
- **Resource Protection**: Prevents high-volume batch processes from overwhelming your workers
- **Robust Redis Connectivity**: Reliable connection handling with retry logic and TLS support
- **Flexible Serialization**: Choose between serialization options (pickle/JSON) based on your needs

## Basic Usage

```python
from celery import Celery
from celery_ranch import lru_task

app = Celery('tasks')

@lru_task(app)
def process_data(data):
    # Process data
    return result

# Using LRU prioritization with a process identifier as the LRU key
result = process_data.lru_delay("bulk_batch_job", data_to_process)
```

## Common Use Cases

- **Batch Jobs vs. Interactive Requests**: Prevent long-running ETL or reporting jobs from blocking user-initiated tasks
- **Background Tasks vs. User Operations**: Balance background maintenance with interactive user operations
- **Scheduled Tasks vs. On-Demand Operations**: Ensure critical on-demand processes aren't starved by scheduled tasks
- **Internal vs. External Requests**: Prioritize customer-facing operations over internal administrative tasks
- **Different Service Tiers**: Give higher priority to premium features while ensuring basic functionality remains responsive

## Advanced Usage

### Weighted Priority

```python
# Set priority weights for different process types (lower value = higher priority)
# 0.5 = 2x priority, 2.0 = 0.5x priority
process_data.set_priority_weight("critical_process", 0.5)  # High priority
process_data.set_priority_weight("background_job", 2.0)    # Low priority

# Submit task with priority and expiry
result = process_data.lru_delay(
    "critical_process",       # LRU key (process identifier)
    data_to_process,          # Task argument
    priority_weight=0.5,      # Priority weight
    expiry=1800               # Expires after 30 minutes
)
```

### Custom Dynamic Weight Functions

```python
from celery_ranch.utils.lru_tracker import LRUKeyMetadata

# Define a custom weight function based on process characteristics
def resource_based_priority(lru_key: str, metadata: LRUKeyMetadata) -> float:
    """Calculate priority based on resource requirements in metadata."""
    # Default weight if no custom data
    if not metadata.custom_data or "resource_impact" not in metadata.custom_data:
        return 1.0
    
    # Higher resource impact = lower priority (higher weight)
    impact = metadata.custom_data.get("resource_impact", 1.0)
    return max(impact, 0.1)  # Ensure positive weight

# Create task with custom weight function
@lru_task(app, weight_function=resource_based_priority)
def process_data(data):
    # Process data
    return result

# Store custom metadata for different processes
process_data.set_custom_data("data_mining_job", "resource_impact", 3.0)  # High impact, lower priority
process_data.set_custom_data("user_report", "resource_impact", 0.5)      # Low impact, higher priority
```

### Process Organization with Tags

```python
# Add tags to categorize different process types
process_data.add_tag("daily_batch", "category", "maintenance")
process_data.add_tag("user_import", "category", "data-ingestion")
process_data.add_tag("user_report", "importance", "critical")

# Find processes by tag
critical_processes = process_data.get_tagged_clients("importance", "critical")
```

### Monitoring

```python
# Get process information
process_info = process_data.get_client_metadata("batch_job_id")
print(f"Process priority: {process_info['weight']}")
print(f"Pending tasks: {process_info['pending_tasks']}")

# Get system status
status = process_data.get_system_status()
print(f"Backlog size: {status['backlog_size']}")
```

## How It Works

Celery Ranch implements a fair scheduling mechanism that works as follows:

1. **Task Interception**: When you call `lru_delay()`, the task doesn't go directly to Celery
2. **Backlog Management**: The task is stored in a backlog, associated with its LRU key (process identifier)
3. **Prioritization Queue**: A lightweight prioritization task is placed in a dedicated queue
4. **Fair Selection**: When a worker processes this task, it:
   - Analyzes all pending processes in the backlog
   - Selects the least recently used process (modified by priority weights)
   - Picks one task from that process's backlog
5. **Execution & Tracking**: The selected task is executed and the LRU timestamp is updated

This approach ensures that:
- No single process can monopolize workers, regardless of submission volume
- Critical processes can still get prioritized with appropriate weights
- All processes get fair access to computing resources
- The system naturally adapts to changing workloads

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

### Publishing to PyPI

See [PyPI Publishing Guide](docs/pypi_publishing.md) for detailed instructions on how to publish the package to PyPI.

### Running Tests

The project uses pytest for testing:

```bash
# Run all tests
pytest

# Run tests with coverage
pytest --cov=celery_ranch

# Generate HTML coverage report
pytest --cov=celery_ranch --cov-report=html
```

### Code Quality

We use several tools to ensure code quality:

```bash
# Run linters
flake8 celery_ranch
pylint celery_ranch

# Format code
black .
isort .

# Type checking
mypy .
```

### Contribution Guidelines

1. **Fork the repository** and create a feature branch from `main`.
2. **Write tests** for new features or bug fixes.
3. **Ensure all tests pass** and the code meets quality standards.
4. **Update documentation** if necessary.
5. **Submit a pull request** with a clear description of the changes.

#### Pull Request Process

1. Update the README.md or documentation with details of changes if appropriate.
2. Update the tests to reflect any changes to the functionality.
3. The PR should work for Python 3.8, 3.9, and 3.10.
4. Select the appropriate version bump label, if any:
   - `bump:patch`: Bug fixes and minor updates (0.1.0 → 0.1.1)
   - `bump:minor`: New features (0.1.0 → 0.2.0) 
   - `bump:major`: Breaking changes (0.1.0 → 1.0.0)
5. PRs will be merged once they receive approval from maintainers.

#### Automated Releases

When a PR with a version bump label is merged to main:

1. The version is automatically incremented in setup.py and __init__.py
2. The updated package is automatically published to PyPI
3. A new entry is created in the package's release history

This automation ensures that new versions are released as soon as approved changes are merged.

### Code of Conduct

- Be respectful and inclusive in your communications.
- Focus on constructive feedback and collaboration.
- Help create a positive and supportive environment for all contributors.

## Supporting Celery Ranch

If you find Celery Ranch useful in your projects, please consider supporting its development! See our [Sponsorship Guide](docs/sponsorship.md) for more information on how you can contribute.

## License

MIT
