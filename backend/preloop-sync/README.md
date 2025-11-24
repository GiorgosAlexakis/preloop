# Preloop Sync

Preloop Sync is a system that scans multiple issue trackers across different user accounts, extracts information about issues for each accessible project, and maintains a PostgreSQL database with vector embeddings for advanced querying and analysis. It's part of Preloop AI, a platform for issue tracking and analysis. It requires SpaceModels that provides the database schema and vector embeddings.

## Features

- Multi-account support for tracker scanning
- Integration with various issue trackers (GitHub, GitLab, Jira, Linear)
- Fetches issue comments for supported trackers (currently GitLab, GitHub, Jira)
- Vector embeddings for similarity search
- Read-only operation (never modifies trackers)
- Efficient incremental updates

## Installation

### Prerequisites

- Python 3.8 or higher
- PostgreSQL database
- Access to issue trackers

### From Source

```bash
git clone https://github.com/spacecode-ai/preloop-ai.git
cd preloop-ai/backend/preloop-sync
pip install -e .
```

## Configuration

Create a `.env` file in the project root with the following variables:

```
# Database configuration
DATABASE_URL=postgresql://username:password@localhost:5432/preloop

# Logging configuration
LOG_LEVEL=INFO
LOG_FILE=/path/to/logs/preloop_sync.log
```

### CLI Commands

Check the system status:

```bash
preloop-sync status
```

Detailed status (including accounts and trackers):

```bash
preloop-sync status -v
```

List trackers for an account:

```bash
preloop-sync list-trackers ACCOUNT_ID
```

Check system configuration:

```bash
preloop-sync check
```

Scan all active accounts and their associated trackers in a single, synchronous run:

```bash
preloop-sync scan all [--verbose] [--force-update]
```

This command performs a one-time scan of all configured and active accounts and trackers. It fetches organizations, projects, and issues, updating the database accordingly. Upon completion, it prints summary statistics of the scan.

Note: This command performs a *single* scan run. For continuous, scheduled, or periodic updates, use the `preloop-sync scheduler start` command instead.

### Continuous Update Service

Preloop Sync includes a scheduler service that continuously updates the database with changes from trackers. The service uses polling for all trackers.

**Starting the service:**

```bash
preloop-sync scheduler
```

This starts the service in the foreground.

**Using NATS task queue:**

You can also configure a NATS_URL environment variable to run the scheduler as a NATS task.
```bash
NATS_URL=nats://localhost:4222 preloop-sync scheduler
```

Then you can start the preloop-sync worker that will process the tasks from the NATS queue.
```bash
preloop-sync worker
```
Service options:

```
--log-level LEVEL    Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
```

**Service Configuration:**

Configure the service in your `.env` file:

```
# Service configuration
SERVICE_POLL_INTERVAL=90       # Poll interval in seconds for all trackers
```
