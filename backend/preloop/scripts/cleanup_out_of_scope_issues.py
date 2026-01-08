"""
Database maintenance script to cleanup issues, comments, and embeddings
that are out of scope according to tracker scope rules.

This script:
1. Identifies issues that belong to projects not matching tracker scope rules
2. Lists the issues to be deleted
3. Asks for user confirmation
4. Deletes issues, their comments, and embeddings

Usage:
    python -m preloop.scripts.cleanup_out_of_scope_issues --account-id <uuid>
    python -m preloop.scripts.cleanup_out_of_scope_issues --tracker-id <uuid>
    python -m preloop.scripts.cleanup_out_of_scope_issues --dry-run
"""

import argparse
import logging
import sys
from typing import List, Optional

from sqlalchemy.orm import Session

from preloop.models.db.session import get_db_session
from preloop.models.models.comment import Comment
from preloop.models.models.issue import Issue, IssueEmbedding
from preloop.models.models.project import Project
from preloop.models.models.tracker import Tracker
from preloop.models.models.tracker_scope_rule import TrackerScopeRule

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def get_out_of_scope_issues(
    db: Session,
    account_id: Optional[str] = None,
    tracker_id: Optional[str] = None,
) -> List[Issue]:
    """
    Find all issues that are out of scope according to tracker scope rules.

    Args:
        db: Database session
        account_id: Optional account ID to filter by
        tracker_id: Optional tracker ID to filter by

    Returns:
        List of Issue objects that are out of scope
    """
    # Build query for all issues
    query = (
        db.query(Issue)
        .join(Project)
        .join(Project.organization)
        .join(Project.organization.property.mapper.class_.tracker)
    )

    # Apply filters
    if account_id:
        query = query.filter(Tracker.account_id == account_id)
    if tracker_id:
        query = query.filter(Tracker.id == tracker_id)

    # Only check active, non-deleted trackers
    query = query.filter(Tracker.is_active, Tracker.is_deleted.is_(False))

    all_issues = query.all()
    out_of_scope_issues = []

    # Check each issue against scope rules
    for issue in all_issues:
        project = issue.project
        tracker = project.organization.tracker

        # Get scope rules for this tracker
        rules = (
            db.query(TrackerScopeRule)
            .filter(TrackerScopeRule.tracker_id == tracker.id)
            .all()
        )

        # Build rule sets (same logic as scanner/core.py)
        org_inclusions = {
            r.identifier
            for r in rules
            if r.scope_type == "ORGANIZATION" and r.rule_type == "INCLUDE"
        }
        project_inclusions = {
            r.identifier
            for r in rules
            if r.scope_type == "PROJECT" and r.rule_type == "INCLUDE"
        }
        project_exclusions = {
            r.identifier
            for r in rules
            if r.scope_type == "PROJECT" and r.rule_type == "EXCLUDE"
        }

        is_out_of_scope = False

        # Check organization inclusion (required)
        if project.organization.identifier not in org_inclusions:
            is_out_of_scope = True
            logger.debug(
                f"Issue {issue.key} out of scope - organization {project.organization.identifier} "
                f"not in inclusion list"
            )

        # Check project exclusion
        if project.identifier in project_exclusions:
            is_out_of_scope = True
            logger.debug(
                f"Issue {issue.key} out of scope - project {project.identifier} in exclusion list"
            )

        # Check project inclusion (if any inclusion rules exist)
        if project_inclusions and project.identifier not in project_inclusions:
            is_out_of_scope = True
            logger.debug(
                f"Issue {issue.key} out of scope - project {project.identifier} "
                f"not in inclusion list"
            )

        if is_out_of_scope:
            out_of_scope_issues.append(issue)

    return out_of_scope_issues


def delete_out_of_scope_issues(db: Session, issues: List[Issue]) -> dict:
    """
    Delete the given issues and their related data (comments, embeddings).

    Args:
        db: Database session
        issues: List of issues to delete

    Returns:
        Dictionary with counts of deleted items
    """
    issue_ids = [issue.id for issue in issues]

    # Count related records
    comment_count = db.query(Comment).filter(Comment.issue_id.in_(issue_ids)).count()
    embedding_count = (
        db.query(IssueEmbedding).filter(IssueEmbedding.issue_id.in_(issue_ids)).count()
    )

    # Delete related records first (foreign key constraints)
    logger.info(f"Deleting {comment_count} comments...")
    db.query(Comment).filter(Comment.issue_id.in_(issue_ids)).delete(
        synchronize_session=False
    )

    logger.info(f"Deleting {embedding_count} embeddings...")
    db.query(IssueEmbedding).filter(IssueEmbedding.issue_id.in_(issue_ids)).delete(
        synchronize_session=False
    )

    # Delete issues
    logger.info(f"Deleting {len(issues)} issues...")
    db.query(Issue).filter(Issue.id.in_(issue_ids)).delete(synchronize_session=False)

    db.commit()

    return {
        "issues": len(issues),
        "comments": comment_count,
        "embeddings": embedding_count,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Cleanup out-of-scope issues from the database"
    )
    parser.add_argument(
        "--account-id",
        help="Filter by account ID (UUID)",
        type=str,
    )
    parser.add_argument(
        "--tracker-id",
        help="Filter by tracker ID (UUID)",
        type=str,
    )
    parser.add_argument(
        "--dry-run",
        help="Show what would be deleted without actually deleting",
        action="store_true",
    )
    parser.add_argument(
        "--yes",
        "-y",
        help="Skip confirmation prompt",
        action="store_true",
    )

    args = parser.parse_args()

    # Get database session
    db = next(get_db_session())

    try:
        # Find out-of-scope issues
        logger.info("Scanning for out-of-scope issues...")
        out_of_scope_issues = get_out_of_scope_issues(
            db, account_id=args.account_id, tracker_id=args.tracker_id
        )

        if not out_of_scope_issues:
            logger.info("✅ No out-of-scope issues found!")
            return 0

        # Display summary
        logger.info(f"\n{'=' * 80}")
        logger.info(f"Found {len(out_of_scope_issues)} out-of-scope issues:")
        logger.info(f"{'=' * 80}\n")

        # Group by tracker and project for better readability
        by_tracker = {}
        for issue in out_of_scope_issues:
            tracker_id = issue.project.organization.tracker.id
            tracker_name = issue.project.organization.tracker.name
            project_name = issue.project.name

            if tracker_id not in by_tracker:
                by_tracker[tracker_id] = {
                    "name": tracker_name,
                    "projects": {},
                }

            if project_name not in by_tracker[tracker_id]["projects"]:
                by_tracker[tracker_id]["projects"][project_name] = []

            by_tracker[tracker_id]["projects"][project_name].append(issue)

        for tracker_id, tracker_data in by_tracker.items():
            logger.info(f"Tracker: {tracker_data['name']} ({tracker_id})")
            for project_name, issues in tracker_data["projects"].items():
                logger.info(f"  Project: {project_name}")
                for issue in issues[:5]:  # Show first 5 issues
                    logger.info(
                        f"    - {issue.key}: {issue.title[:60]}{'...' if len(issue.title or '') > 60 else ''}"
                    )
                if len(issues) > 5:
                    logger.info(f"    ... and {len(issues) - 5} more issues")
            logger.info("")

        # Count related records
        issue_ids = [issue.id for issue in out_of_scope_issues]
        comment_count = (
            db.query(Comment).filter(Comment.issue_id.in_(issue_ids)).count()
        )
        embedding_count = (
            db.query(IssueEmbedding)
            .filter(IssueEmbedding.issue_id.in_(issue_ids))
            .count()
        )

        logger.info(f"{'=' * 80}")
        logger.info("Summary:")
        logger.info(f"  Issues to delete: {len(out_of_scope_issues)}")
        logger.info(f"  Comments to delete: {comment_count}")
        logger.info(f"  Embeddings to delete: {embedding_count}")
        logger.info(f"{'=' * 80}\n")

        if args.dry_run:
            logger.info("🔍 DRY RUN - No changes will be made")
            return 0

        # Confirm deletion
        if not args.yes:
            response = input(
                "⚠️  Are you sure you want to delete these issues? This cannot be undone. [y/N]: "
            )
            if response.lower() not in ["y", "yes"]:
                logger.info("❌ Deletion cancelled")
                return 1

        # Perform deletion
        logger.info("\n🗑️  Starting deletion...")
        result = delete_out_of_scope_issues(db, out_of_scope_issues)

        logger.info(f"\n{'=' * 80}")
        logger.info("✅ Deletion complete!")
        logger.info(f"  Issues deleted: {result['issues']}")
        logger.info(f"  Comments deleted: {result['comments']}")
        logger.info(f"  Embeddings deleted: {result['embeddings']}")
        logger.info(f"{'=' * 80}\n")

        return 0

    except Exception as e:
        logger.error(f"❌ Error during cleanup: {e}", exc_info=True)
        db.rollback()
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
