# SpaceModels Library

SpaceModels is a SQLAlchemy-based ORM library that provides a comprehensive set of models and CRUD operations for SpaceBridge and related applications. This library aims to unify data models across the SpaceBridge ecosystem.

## Installation

1. Clone the repository:
```bash
git clone https://github.com/spacecode/spacemodels.git
cd spacemodels
```

2. Create a virtual environment (optional but recommended):
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install the package:
```bash
pip install -r requirements.txt
pip install -e .  # Install in development mode
```

4. Set up your database:
```bash
# For PostgreSQL (recommended for production)
export DATABASE_URL="postgresql+psycopg://user:password@localhost/spacemodels"

```

## Usage

```python
from spacemodels.db.session import get_db_session
from spacemodels.crud import crud_account, crud_tracker

# Get database session
db = next(get_db_session())

# Create a new account
new_account = crud_account.create(
    db, 
    obj_in={
        "username": "johndoe",
        "email": "john@example.com",
        "full_name": "John Doe",
        "hashed_password": "hashed_password_here"
    }
)

# Set up a GitHub tracker for the account
new_tracker = crud_tracker.create(
    db,
    obj_in={
        "name": "GitHub Issues",
        "tracker_type": "github",
        "account_id": new_account.id,
        "api_key": "github_token_here",
        "connection_details": {
            "repository": "owner/repo"
        }
    }
)

# Always close the session when done
db.close()
```

See [Usage Examples](docs/usage_examples.md) for more detailed examples.
