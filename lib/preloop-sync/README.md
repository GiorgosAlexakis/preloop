# SpaceSync

SpaceSync is a read-only system that scans multiple issue trackers across different user accounts, extracts information about issues for each accessible project, and maintains a PostgreSQL database with vector embeddings for advanced querying and analysis.

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
git clone https://github.com/yourusername/spacesync.git
cd spacesync
pip install -e .
```

## Configuration

Create a `.env` file in the project root with the following variables:

```
# Database configuration
DATABASE_URL=postgresql://username:password@localhost:5432/spacesync

# Logging configuration
LOG_LEVEL=INFO
LOG_FILE=/path/to/logs/spacesync.log
```

### CLI Commands

Check the system status:

```bash
spacesync status
```

Detailed status (including accounts and trackers):

```bash
spacesync status -v
```

List trackers for an account:

```bash
spacesync list-trackers ACCOUNT_ID
```

Check system configuration:

```bash
spacesync check
```

Scan all active accounts and their associated trackers in a single, synchronous run:

```bash
spacesync scan all [--verbose] [--force-update]
```

This command performs a one-time scan of all configured and active accounts and trackers. It fetches organizations, projects, and issues, updating the database accordingly. Upon completion, it prints summary statistics of the scan.

Note: This command performs a *single* scan run. For continuous, scheduled, or periodic updates, use the `spacesync scheduler start` command instead.

### Continuous Update Service

SpaceSync includes a service that continuously updates the database with changes from trackers. The service uses polling for all trackers.

**Starting the service:**

```bash
spacesync service start --foreground
```

This starts the service in the foreground. Remove the `--foreground` flag to run it in the background.

**Using the standalone script:**

You can also run the service using the standalone script:

```bash
python scripts/run_service.py --foreground
```

Service options:

```
--foreground         Run in foreground (don't daemonize)
--reload-interval N  Interval (in seconds) to reload tracker list
--log-level LEVEL    Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
```

**Service Configuration:**

Configure the service in your `.env` file:

```
# Service configuration
SERVICE_POLL_INTERVAL=90       # Poll interval in seconds for all trackers
```

## Development

### Project Structure

```
spacesync/
├── spacesync/
│   ├── __init__.py
│   ├── __main__.py
│   ├── config.py
│   ├── exceptions.py
│   ├── utils.py
│   ├── db/
│   │   ├── __init__.py
│   │   ├── session.py
│   │   ├── models.py
│   │   └── crud.py
│   └── cli/
│       ├── __init__.py
│       └── commands.py
├── setup.py
├── README.md
├── .env.template
└── ROADMAP.md
