"""
A script to scan all connected trackers for registered webhooks.

This script performs the following actions:
1.  It goes over the webhooks in the db to see if they are properly registered with each tracker.
2.  If they are not, it asks the user if we should delete them from the db or if we should try to create them in the tracker.
3.  It then scans the trackers themselves to see if they have any webhooks registered on each org/project we have access to.
4.  It displays all detected webhooks and should highlight the webhooks that correspond to this Preloop instance
    (check if the PRELOOP_URL env var is a prefix of the webhook URL).
5.  For each detected webhook of the specified Preloop instance check if it is properly registered in the database.
6.  If not, then ask the user if it should be deleted from the tracker.
7.  Provide command line options to always delete or never delete.
"""

import argparse
import os
from typing import List

from sqlalchemy import or_
from sqlalchemy.orm import Session, aliased, joinedload

from preloop.models.db.session import get_db_session
from preloop.models.models import Organization, Project, Tracker, Webhook
from preloop.sync.scanner.core import TrackerClient
from preloop.sync.exceptions import TrackerAuthenticationError


def verify_webhooks(db: Session, auto_delete: bool = False, auto_create: bool = False):
    """
    Verifies webhooks for all active trackers.
    """
    preloop_url = os.getenv("PRELOOP_URL")
    if not preloop_url:
        print("PRELOOP_URL environment variable not set. Cannot verify webhooks.")
        return

    org_from_project = aliased(Organization)
    trackers = (
        db.query(Tracker).filter(Tracker.is_active, Tracker.is_deleted.is_(False)).all()
    )
    for tracker in trackers:
        print(f"Verifying webhooks for tracker {tracker.id} ({tracker.tracker_type})")
        client = TrackerClient(tracker)

        # 1. Check webhooks in the DB against the tracker
        webhook_ids_query = (
            db.query(Webhook.id)
            .outerjoin(Organization, Webhook.organization_id == Organization.id)
            .outerjoin(Project, Webhook.project_id == Project.id)
            .outerjoin(org_from_project, Project.organization_id == org_from_project.id)
            .filter(
                or_(
                    Organization.tracker_id == tracker.id,
                    org_from_project.tracker_id == tracker.id,
                )
            )
            .distinct()
        )
        db_webhooks: List[Webhook] = (
            db.query(Webhook)
            .options(
                joinedload(Webhook.organization),
                joinedload(Webhook.project).joinedload(Project.organization),
            )
            .filter(Webhook.id.in_(webhook_ids_query))
            .all()
        )
        client_failure = False
        for db_webhook in db_webhooks:
            try:
                is_registered = client.client.is_webhook_registered(db_webhook)
            except TrackerAuthenticationError as e:
                client_failure = True
                print(
                    f"Failed to authenticate with tracker {tracker.name} - {tracker.id}"
                )
                break
            except Exception as e:
                client_failure = True
                print(
                    f"Failed to fetch webhook from tracker {tracker.name} - {tracker.id}"
                )
                break
            if not is_registered:
                print(
                    f"  Webhook {db_webhook.id} ({db_webhook.url}) is in the DB but not registered in the tracker."
                )
                if auto_create:
                    print("    --auto-create is set, attempting to create webhook.")
                    client.client.register_webhook(
                        db, db_webhook.organization, db_webhook.url, db_webhook.secret
                    )
                elif auto_delete:
                    print("    --auto-delete is set, deleting webhook from DB.")
                    db.delete(db_webhook)
                    db.commit()
                else:
                    choice = input(
                        "    Delete from DB (d), try to create in tracker (c), or ignore (i)? [d/c/i]: "
                    ).lower()
                    if choice == "d":
                        db.delete(db_webhook)
                        db.commit()
                        print("    Webhook deleted from DB.")
                    elif choice == "c":
                        client.client.register_webhook(
                            db,
                            db_webhook.organization,
                            db_webhook.url,
                            db_webhook.secret,
                        )
                        print("    Attempted to create webhook in tracker.")
            else:
                print(
                    f"  Webhook {db_webhook.id} ({db_webhook.url}) is correctly registered."
                )

        if client_failure:
            continue
        # 2. Scan tracker for webhooks and check against DB
        organizations = (
            db.query(Organization).filter(Organization.tracker_id == tracker.id).all()
        )
        for organization in organizations:
            if tracker.tracker_type in ["gitlab", "github"]:
                tracker_webhooks = client.client.get_webhooks(organization.identifier)
            else:
                tracker_webhooks = client.client.get_webhooks()
            for tracker_webhook in tracker_webhooks:
                webhook_url = tracker_webhook.get("url")
                if webhook_url and webhook_url.startswith(preloop_url):
                    print(f"  Found Preloop webhook in tracker: {webhook_url}")
                    db_webhook = (
                        db.query(Webhook)
                        .filter(Webhook.url == webhook_url)
                        .outerjoin(
                            Organization, Webhook.organization_id == Organization.id
                        )
                        .outerjoin(Project, Webhook.project_id == Project.id)
                        .outerjoin(
                            org_from_project,
                            Project.organization_id == org_from_project.id,
                        )
                        .filter(
                            or_(
                                Organization.tracker_id == tracker.id,
                                org_from_project.tracker_id == tracker.id,
                            )
                        )
                        .first()
                    )
                    if not db_webhook:
                        print(
                            f"    Webhook {webhook_url} is in the tracker but not in the DB."
                        )
                        if auto_delete:
                            print(
                                "    --auto-delete is set, deleting webhook from tracker."
                            )
                            client.client.delete_webhook(tracker_webhook)
                        else:
                            choice = input(
                                "    Delete from tracker (d) or ignore (i)? [d/i]: "
                            ).lower()
                            if choice == "d":
                                client.client.delete_webhook(tracker_webhook)
                                print("    Webhook deleted from tracker.")
                elif webhook_url:
                    print(f"  Found other webhook in tracker: {webhook_url}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Verify webhooks for all active trackers."
    )
    parser.add_argument(
        "--auto-delete", action="store_true", help="Always delete mismatched webhooks."
    )
    parser.add_argument(
        "--auto-create", action="store_true", help="Always create missing webhooks."
    )
    args = parser.parse_args()

    db_session = next(get_db_session())
    verify_webhooks(db_session, args.auto_delete, args.auto_create)
