#!/usr/bin/env python
"""
Script to create all tables from SQLAlchemy models.
This is useful for CI environments where you want a clean database schema.
"""

import os
import sys

import click
from sqlalchemy import create_engine

# Import Base and all model classes to register them with Base.metadata
from spacemodels.models.base import Base
from spacemodels.models import (  # noqa: F401
    Account,
    AIModel,
    ApiKey,
    ApiUsage,
    ApprovalPolicy,
    ApprovalRequest,
    ApprovalRule,
    AuditLog,
    ClientVersionLog,
    Comment,
    EmbeddingModel,
    Flow,
    FlowExecution,
    Issue,
    IssueComplianceResult,
    IssueDuplicate,
    IssueEmbedding,
    IssueRelationship,
    IssueSet,
    MCPServer,
    MCPTool,
    MonthlyUsage,
    Organization,
    Permission,
    Plan,
    Project,
    Role,
    RolePermission,
    Subscription,
    Team,
    TeamMembership,
    TeamRole,
    ToolConfiguration,
    Tracker,
    TrackerScopeRule,
    User,
    UserInvitation,
    UserRole,
    Webhook,
)


@click.command()
@click.option("--force", is_flag=True, help="Skip confirmation")
def create_tables(force: bool):
    """
    Create all tables from SQLAlchemy models.
    """
    # Get database connection string from environment
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        click.echo("ERROR: DATABASE_URL environment variable not set.")
        sys.exit(1)

    if not force:
        click.echo("This will create all database tables from SQLAlchemy models.")
        click.echo(f"Database: {db_url}")
        if not click.confirm("Continue?"):
            click.echo("Operation cancelled.")
            sys.exit(0)

    try:
        # Create engine
        engine = create_engine(db_url)

        # Create all tables
        click.echo("Creating all tables...")
        Base.metadata.create_all(bind=engine)
        click.echo("All tables created successfully.")

    except Exception as e:
        click.echo(f"ERROR: Failed to create tables: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    create_tables()
