# Ranch Library Enhancements

This document summarizes the enhancements made to the Ranch library to improve its reliability, performance, and feature set.

## GitHub Installation Support

While PyPI registrations are temporarily unavailable, we've added support for installing the package directly from GitHub.

### Installation Methods

#### Basic Installation
```bash
pip install git+https://github.com/teleos-consulting/celery-ranch.git
```

#### Version-specific Installation
```bash
pip install git+https://github.com/teleos-consulting/celery-ranch.git@v0.1.0
```

#### Installation with Redis Support
```bash
pip install "git+https://github.com/teleos-consulting/celery-ranch.git#egg=celery-ranch[redis]"
```

### GitHub Release Automation

We've enhanced our GitHub Actions workflows to:

1. Automatically create GitHub Releases when version tags are pushed
2. Attach built package distributions to GitHub Releases
3. Conditionally publish to PyPI (when it becomes available again)
4. Support tag-based versioning

### How to Tag a Version

To create a new release:

```bash
# Ensure changes are committed to main/master
git checkout main
git pull

# Create and push a version tag
git tag v0.1.1
git push origin v0.1.1
```

This will trigger the GitHub Actions workflow to:
1. Run tests
2. Build package distributions
3. Create a GitHub Release with attached distributions
4. (Conditionally) Publish to PyPI if PYPI_ENABLED secret is set to 'true'

## Implemented Enhancements

### 1. Redis Connection Handling
- **Connection Pooling**: Added connection pool support for better Redis performance
- **Retry Logic**: Implemented exponential backoff retry for transient Redis errors
- **Error Handling**: Better error handling with detailed logging
- **Connection Validation**: Health checks for Redis connections
- **TLS Support**: Support for Redis connections over TLS/SSL

### 2. Improved Serialization
- **Configurable Serializers**: Added option to choose between pickle and JSON serializers
- **Security Considerations**: Documented security implications of serialization choices
- **Performance Tuning**: Optimized serialization for different use cases

### 3. Weighted LRU Prioritization
- **Priority Weights**: Clients can be assigned different priority weights
- **Configurable Weighting**: Lower values (e.g., 0.5) provide higher priority, higher values (e.g., 2.0) provide lower priority
- **Dynamic Adjustment**: Priority weights can be changed at runtime
- **Fair Scheduling**: Ensures tasks are executed in order of weighted priority

### 4. Task Expiry and Management
- **Automatic Task Expiry**: Tasks can now expire after a specified time
- **Backlog Cleanup**: Background cleanup of expired tasks
- **Task Metadata**: Additional information can be stored with tasks
- **Expiry Configuration**: Configurable at task, client, or global level

### 5. Client Organization with Tags
- **Tagging System**: Clients can be tagged with arbitrary metadata
- **Filtering by Tags**: Ability to retrieve clients by tag values
- **Metadata Association**: Store and retrieve contextual information

### 6. Monitoring and Observability
- **System Status API**: Get current status of the LRU priority system
- **Client Metadata**: Retrieve information about clients and their tasks
- **Backlog Statistics**: Track backlog size, client counts, and expired tasks
- **Detailed Logging**: Comprehensive logging at various levels

### 7. Configuration System
- **Centralized Configuration**: Configure Ranch through Celery app configuration
- **Default Values**: Sensible defaults for all settings
- **Configuration Isolation**: Ranch-specific configuration under `app.conf.ranch`
- **Runtime Updates**: Configuration can be updated at runtime

## Usage Examples

### Basic Usage with Redis and Weighted Priority

```python
from celery import Celery
from ranch import lru_task, SerializerType

app = Celery('tasks', broker='redis://localhost:6379/0')

# Configure Ranch
app.conf.ranch = {
    "redis_prefix": "myapp:",
    "redis_serializer": SerializerType.JSON,
    "redis_key_ttl": 3600,  # 1 hour default expiry
    "redis_use_ssl": True,
    "metrics_enabled": True
}

@lru_task(app)
def process_data(data):
    # Process data
    return result

# Set priority weight for a client (0.5 = 2x priority)
process_data.set_priority_weight("premium_client", 0.5)

# Add tags for organization
process_data.add_tag("premium_client", "type", "premium")

# Submit task with explicit priority and expiry
result = process_data.lru_delay(
    "premium_client",           # LRU key for client
    data_to_process,            # Task argument
    priority_weight=0.5,        # Higher priority (lower number)
    tags={"region": "us-west"}, # Optional metadata 
    expiry=1800                 # Expires after 30 minutes
)

# Get client information
client_info = process_data.get_client_metadata("premium_client")
print(f"Client priority: {client_info['weight']}")
print(f"Pending tasks: {client_info['pending_tasks']}")

# Get system status
status = process_data.get_system_status()
print(f"Total backlog size: {status['backlog_size']}")
```

## Performance Considerations

- The enhanced Redis connection handling significantly improves reliability under load
- Serialization options allow trading off between compatibility (pickle) and speed/safety (JSON)
- Connection pooling reduces connection overhead for frequent Redis operations
- Expired task cleanup prevents backlog accumulation and memory growth
- Weighted prioritization ensures efficient resource allocation based on client importance

### 8. Custom Dynamic Weight Functions
- **Dynamic Priority Calculation**: Provide custom functions to calculate priorities at runtime
- **Custom Data Storage**: Store arbitrary data for clients to use in weight calculations
- **Bid-based Priority**: Example implementation of a bidding system for queue prioritization
- **Flexible Resource Allocation**: Enables complex prioritization schemes beyond static weights
- **Real-time Weight Adjustment**: Weights can be calculated based on current system state

## Future Enhancement Ideas

1. **Metrics Integration**: Prometheus/StatsD integration for real-time monitoring
2. **Administration UI**: Web interface for managing clients, weights, and backlogs
3. **Dynamic Auto-scaling**: Adjust weights based on backlog sizes and processing times
4. **Multi-queue Support**: Distribute tasks across multiple prioritization queues
5. **Cluster Support**: Enhanced support for Redis Cluster deployments