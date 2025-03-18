# SpaceModels Usage Examples

This document contains usage examples for the SpaceModels library.

## Basic Setup

```python
# Import database session
from spacemodels.db.session import get_db_session
from spacemodels.crud import (
    crud_account, crud_tracker, crud_organization, 
    crud_project, crud_issue, crud_embedding_model, 
    crud_issue_embedding
)

# Get database session
db = next(get_db_session())
```

## Creating an Account with a Tracker

```python
# Create a new account
new_account = crud_account.create(
    db, 
    obj_in={
        "username": "johndoe",
        "email": "john@example.com",
        "full_name": "John Doe",
        "hashed_password": "hashed_password_here",
        "is_active": True,
        "meta_data": {
            "timezone": "America/New_York",
            "preferences": {
                "notifications": {
                    "email": True,
                    "in_app": True
                }
            }
        }
    }
)

# Set up a GitHub tracker for the account
new_tracker = crud_tracker.create(
    db,
    obj_in={
        "name": "GitHub Issues",
        "tracker_type": "github",
        "account_id": new_account.id,
        "is_active": True,
        "url": "https://api.github.com",
        "api_key": "encrypted_github_token_here",
        "connection_details": {
            "repository": "owner/repo"
        },
        "meta_data": {
            "app_integration_type": "personal_access_token",
            "rate_limit_remaining": 5000
        }
    }
)
```

## Creating and Managing Organizations

```python
# Create an organization linked to the tracker
new_org = crud_organization.create(
    db, 
    obj_in={
        "name": "Example Organization",
        "identifier": "example-org",
        "description": "This is an example organization",
        "is_active": True,
        "tracker_id": new_tracker.id,
        "meta_data": {
            "industry": "Technology",
            "size": "Medium",
            "location": "San Francisco, CA"
        }
    }
)

# Link the account to the organization with a role
crud_account.add_to_organization(
    db,
    account_id=new_account.id,
    organization_id=new_org.id,
    role="owner"
)

# Create a project in the organization
new_project = crud_project.create(
    db,
    obj_in={
        "name": "Example Project",
        "identifier": "example-project",
        "organization_id": new_org.id,
        "description": "This is an example project",
        "is_active": True,
        "tracker_settings": {
            "project_key": "EXP",  # For JIRA
            "labels": ["spacebridge"]  # For GitHub/GitLab
        },
        "meta_data": {
            "team": "Backend",
            "stage": "Development",
            "custom_fields": {
                "target_release": "v1.0",
                "customer_facing": True
            }
        }
    }
)
```

## Working with Issues

```python
# Create an issue
new_issue = crud_issue.create(
    db,
    obj_in={
        "title": "Example Issue",
        "description": "This is an example issue",
        "status": "open",
        "issue_type": "bug",
        "priority": "high",
        "project_id": new_project.id,
        "tracker_id": new_tracker.id,
        "meta_data": {
            "labels": ["backend", "critical", "customer-reported"],
            "custom_fields": {
                "story_points": 5,
                "reporter_name": "Jane Smith",
                "expected_behavior": "The API should return a 200 status code"
            }
        }
    }
)

# Update issue status
updated_issue = crud_issue.update_status(
    db,
    id=new_issue.id,
    status="in_progress",
    sync_to_tracker=True  # Will sync to external tracker if available
)

# Get issues for a project
project_issues = crud_issue.get_for_project(
    db,
    project_id=new_project.id,
    status="in_progress"  # Optional filter
)
```

## Working with Embeddings

```python
# Set up embedding models
openai_model = crud_embedding_model.create(
    db,
    obj_in={
        "name": "text-embedding-3-large",
        "provider": "openai",
        "version": "v1",
        "dimensions": 3072,
        "is_active": True,
        "meta_data": {
            "context_length": 8191,
            "api_version": "2023-05-15"
        }
    }
)

# Create embeddings for all issues in a project
for issue in project_issues:
    crud_issue_embedding.create_embeddings(
        db,
        issue_id=issue.id,
        force_update=False,  # Won't update existing embeddings
        api_key=None  # For testing, uses random vectors
    )

# Perform similarity search for similar issues
query_vector = [0.1] * 3072  # In a real app, this would be generated from an embedding API
similar_issues = crud_issue_embedding.similarity_search(
    db,
    model_id=openai_model.id,
    query_vector=query_vector,
    limit=5,
    distance_type="cosine"  # Or "euclidean"
)

# Process search results
for issue, similarity_score in similar_issues:
    print(f"Issue: {issue.title} - Similarity: {similarity_score:.2f}")
```

## Using pgvector with PostgreSQL

For production use with PostgreSQL and pgvector:

```python
import os
import openai
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Set up database with pgvector extension
os.environ["DATABASE_URL"] = "postgresql://postgres:postgres@localhost/spacemodels"

# Initialize OpenAI client
openai_client = openai.OpenAI(api_key="your_openai_api_key")

# Create engine and ensure pgvector extension is installed
from spacemodels.db.session import get_engine
from spacemodels.db.vector_types import install_pgvector_extension

engine = get_engine()
install_pgvector_extension(engine)  # Automatically installs pgvector if needed

# Create session
from spacemodels.db.session import get_session_factory
SessionLocal = get_session_factory(engine)
db = SessionLocal()

# Generate real embeddings for a search query
from spacemodels.crud import crud_embedding_model, crud_issue_embedding

# Get the embedding model
model = crud_embedding_model.get_by_name(db, name="text-embedding-3-large")

# Generate embedding for search query using the OpenAI API
response = openai_client.embeddings.create(
    model="text-embedding-3-large",
    input="How do I fix login issues?"
)
query_vector = response.data[0].embedding

# Search for similar issues using pgvector's native vector operations
similar_issues = crud_issue_embedding.similarity_search(
    db,
    model_id=model.id,
    query_vector=query_vector,
    limit=5,
    distance_type="cosine"  # pgvector supports both cosine and euclidean
)

# Process results
for issue, similarity in similar_issues:
    print(f"{issue.title} - {issue.status} - Similarity: {similarity:.4f}")

db.close()
```

The pgvector extension provides optimized vector similarity search operations in PostgreSQL,
making large-scale semantic search much more efficient than in-memory calculations.

## Error Handling

```python
try:
    # Try to create a tracker with an invalid type
    invalid_tracker = crud_tracker.create(
        db,
        obj_in={
            "name": "Invalid Tracker",
            "tracker_type": "invalid",  # Not in TrackerType enum
            "account_id": new_account.id,
            "api_key": "test_api_key"
        }
    )
except ValueError as e:
    print(f"Validation error: {e}")
    
# Error handling for database operations
try:
    # Try to create an organization with a duplicate identifier
    duplicate_org = crud_organization.create(
        db,
        obj_in={
            "name": "Duplicate Organization",
            "identifier": "example-org",  # Already exists
            "tracker_id": new_tracker.id
        }
    )
except Exception as e:
    print(f"Database error: {e}")
    db.rollback()  # Important to roll back transaction on error
```

## Cleanup and Closing

```python
# Always close your database session when done
db.close()
```