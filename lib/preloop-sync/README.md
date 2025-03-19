# SpaceSync

SpaceSync is a read-only system that scans multiple issue trackers across different user accounts, extracts information about issues for each accessible project, and maintains a PostgreSQL database with vector embeddings for advanced querying and analysis.

## Features

- Multi-account support for tracker scanning
- Integration with various issue trackers (GitHub, GitLab, Jira, Linear)
- Vector embeddings for semantic search
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

## Usage

### Database Initialization

SpaceSync requires a properly initialized PostgreSQL database. Follow these steps to set up the database:

1. **Initialize the database schema:**

```bash
python scripts/init_db.py --force
```

This command creates all necessary tables in the PostgreSQL database defined in your `.env` file. The `--force` flag will drop existing tables if they exist.

2. **Create an admin account:**

```bash
python scripts/create_account.py --force
```

This creates an initial user account with configured trackers from the settings in your `.env` file. The `--force` flag will overwrite existing accounts with the same username.

3. **Scan all trackers to populate the database:**

```bash
spacesync scan all
```

This command scans all configured trackers for the accounts in the database, fetching organizations, projects, and issues.

4. **(Optional) Drop all tables:**

If you need to reset the database completely:

```bash
python scripts/drop_tables.py --force
```

This will drop all tables from the database. Use with caution, as this will delete all data.

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

Scan all accounts and their trackers:

```bash
spacesync scan all
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
```
