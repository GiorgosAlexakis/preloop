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

### CLI Commands

Check the system status:

```bash
spacesync status
```

List trackers for an account:

```bash
spacesync list-trackers ACCOUNT_ID
```

Check system configuration:

```bash
spacesync check
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

## License

[MIT License](LICENSE)
