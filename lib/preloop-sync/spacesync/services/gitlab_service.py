"""
GitLab-specific tracker update service.
"""

import secrets
import threading
from typing import Any, Dict

import gitlab
from flask import Flask, jsonify, request
from sqlalchemy.orm import Session

from spacemodels.crud import (
    crud_issue,
    crud_issue_embedding,
    crud_organization,
    crud_project,
)
from spacemodels.models import Organization, Project, Tracker

from ..config import SERVICE_HOST, SERVICE_PORT, logger
from .base import WebhookTrackerUpdateService


class GitLabWebhookUpdateService(WebhookTrackerUpdateService):
    """
    GitLab webhook-based tracker update service.

    This service registers webhooks with GitLab to receive updates
    for issues in real-time, rather than polling periodically.
    """

    def __init__(
        self,
        db: Session,
        tracker: Tracker,
        host: str = SERVICE_HOST,
        port: int = SERVICE_PORT,
    ):
        """
        Initialize the GitLab webhook update service.

        Args:
            db: Database session
            tracker: Tracker model
            host: Host to listen on (default: 0.0.0.0)
            port: Port to listen on (default: 5000)
        """
        super().__init__(db, tracker)
        self.host = host
        self.port = port
        self.app = Flask(f"gitlab-webhook-{tracker.id}")
        self.webhook_secret = secrets.token_hex(16)
        self.webhook_url = None
        self.server_thread = None
        self.gitlab_client = None
        self.webhook_ids = []

        # Set up Flask routes
        self.setup_routes()

    def setup_routes(self) -> None:
        """Set up Flask routes for webhook handling."""

        @self.app.route("/webhooks/gitlab/<tracker_id>", methods=["POST"])
        def webhook_handler(tracker_id):
            # Verify this webhook is for the right tracker
            if tracker_id != str(self.tracker.id):
                logger.warning(f"Received webhook for unknown tracker ID: {tracker_id}")
                return jsonify({"status": "error", "message": "Unknown tracker"}), 404

            # Verify signature if it exists
            if not self._verify_webhook_signature(request):
                logger.warning(
                    f"Invalid webhook signature for tracker {self.tracker.id}"
                )
                return jsonify({"status": "error", "message": "Invalid signature"}), 401

            # Process the webhook payload
            try:
                payload = request.json
                self._process_webhook_payload(payload)
                return jsonify({"status": "success"}), 200
            except Exception as e:
                logger.error(
                    f"Error processing webhook for tracker {self.tracker.id}: {str(e)}"
                )
                return jsonify({"status": "error", "message": str(e)}), 500

    def _verify_webhook_signature(self, request) -> bool:
        """
        Verify the GitLab webhook signature.

        Args:
            request: Flask request object

        Returns:
            True if signature is valid, False otherwise
        """
        # If secret token is set, verify X-Gitlab-Token header
        if self.webhook_secret:
            token = request.headers.get("X-Gitlab-Token")
            if not token:
                logger.warning("Missing X-Gitlab-Token header")
                return False

            if token != self.webhook_secret:
                logger.warning("Invalid X-Gitlab-Token")
                return False

        return True

    def _process_webhook_payload(self, payload: Dict[str, Any]) -> None:
        """
        Process a GitLab webhook payload.

        Args:
            payload: GitLab webhook payload
        """
        event_type = request.headers.get("X-Gitlab-Event")

        if not event_type:
            logger.warning("Missing X-Gitlab-Event header")
            return

        logger.info(f"Received GitLab webhook event: {event_type}")

        # Handle various event types
        if event_type == "Issue Hook":
            self._handle_issue_event(payload)
        elif event_type == "Merge Request Hook":
            # Not currently handled, but could be in the future
            pass
        elif event_type == "Push Hook":
            # Not currently handled, but could be in the future
            pass

    def _handle_issue_event(self, payload: Dict[str, Any]) -> None:
        """
        Handle GitLab issue event.

        Args:
            payload: GitLab issue webhook payload
        """
        # Extract necessary information
        object_attributes = payload.get("object_attributes", {})
        project = payload.get("project", {})

        # Get project and issue IDs
        project_id = project.get("id")
        issue_id = object_attributes.get("id")

        if not project_id or not issue_id:
            logger.warning("Missing project_id or issue_id in payload")
            return

        logger.info(f"Processing issue update: project={project_id}, issue={issue_id}")

        # Find organization for this project
        orgs = crud_organization.get_for_tracker(self.db, tracker_id=self.tracker.id)

        for org in orgs:
            # Find project in database
            db_project = crud_project.get_by_identifier(
                self.db, organization_id=org.id, identifier=str(project_id)
            )

            if db_project:
                # Found the project, update the issue
                self._update_issue(org, db_project, issue_id)
                return

        logger.warning(
            f"Could not find project with identifier {project_id} for tracker {self.tracker.id}"
        )

    def _update_issue(
        self, organization: Organization, project: Project, issue_id: str
    ) -> None:
        """
        Update an issue in the database.

        Args:
            organization: Organization model
            project: Project model
            issue_id: External ID of the issue
        """
        # Fetch the issue data from GitLab
        try:
            # Get issue data from tracker
            issue_data = self.client.client.get_issue(
                organization.identifier, project.identifier, issue_id
            )

            # Transform data for database
            issue_create_data = self.client.client.transform_issue(
                issue_data, project.id
            )

            # Find existing issues for this project
            existing_issues = crud_issue.get_for_project(self.db, project_id=project.id)

            # Find the matching issue by external_id
            issue = next(
                (
                    i
                    for i in existing_issues
                    if i.external_id == issue_create_data["external_id"]
                ),
                None,
            )

            content_changed = False

            if issue:
                # Check if content has changed
                if (
                    issue.title != issue_create_data["title"]
                    or issue.description != issue_create_data["description"]
                ):
                    content_changed = True

                # Update existing
                issue = crud_issue.update(
                    self.db, db_obj=issue, obj_in=issue_create_data
                )
                logger.info(f"Updated issue {issue.id} ({issue.title}) via webhook")
            else:
                # Create new - always need embedding
                issue = crud_issue.create(self.db, obj_in=issue_create_data)
                content_changed = True
                logger.info(f"Created issue {issue.id} ({issue.title}) via webhook")

            # Update embeddings if content changed
            if content_changed:
                # Create or update embeddings
                crud_issue_embedding.create_embeddings(self.db, issue_id=issue.id)
                logger.info(
                    f"Generated embeddings for issue {issue.id} - '{issue.title}'"
                )

        except Exception as e:
            logger.error(
                f"Error updating issue {issue_id} for project {project.id}: {str(e)}"
            )

    def _init_gitlab_client(self) -> None:
        """Initialize the GitLab client."""
        if not self.gitlab_client:
            gitlab_url = self.tracker.url or "https://gitlab.com"

            self.gitlab_client = gitlab.Gitlab(
                url=gitlab_url, private_token=self.tracker.api_key
            )
            self.gitlab_client.auth()

    def register_webhook(self) -> bool:
        """
        Register webhooks with GitLab.
        """
        self._init_gitlab_client()

        # Get all projects from GitLab
        organization_data_list = self.client.client.get_organizations()

        for org_data in organization_data_list:
            project_data_list = self.client.client.get_projects(org_data["id"])

            for proj_data in project_data_list:
                project_id = proj_data["id"]

                # Get GitLab project
                gl_project = self.gitlab_client.projects.get(project_id)

                # Create webhook URL
                webhook_url = f"https://{self.host}/webhooks/gitlab/{self.tracker.id}"
                self.webhook_url = webhook_url

                # Register webhook
                hook = gl_project.hooks.create(
                    {
                        "url": webhook_url,
                        "token": self.webhook_secret,
                        "push_events": False,
                        "issues_events": True,
                        "merge_requests_events": False,
                        "tag_push_events": False,
                        "note_events": False,
                        "job_events": False,
                        "pipeline_events": False,
                        "wiki_page_events": False,
                        "enable_ssl_verification": True,
                    }
                )

                self.webhook_ids.append((project_id, hook.id))
                logger.info(f"Registered GitLab webhook for project {project_id}")

    def unregister_webhook(self) -> bool:
        """
        Unregister webhooks from GitLab.
        """
        self._init_gitlab_client()

        for project_id, hook_id in self.webhook_ids:
            # Get GitLab project
            gl_project = self.gitlab_client.projects.get(project_id)

            # Delete webhook
            gl_project.hooks.delete(hook_id)
            logger.info(f"Unregistered GitLab webhook for project {project_id}")

        self.webhook_ids = []

    def setup(self) -> bool:
        """
        Set up the webhook update service.

        Returns:
            True if setup was successful, False otherwise
        """
        # Register webhooks first
        if not super().setup():
            return False

        # Start Flask server
        return True

    def start(self) -> None:
        """Start the webhook update service."""
        super().start()

        # Start Flask server in a separate thread
        self.server_thread = threading.Thread(target=self._run_flask_server)
        self.server_thread.daemon = True
        self.server_thread.start()

        logger.info(f"Started GitLab webhook service for tracker {self.tracker.id}")

    def _run_flask_server(self) -> None:
        """Run the Flask server."""
        self.app.run(host=self.host, port=self.port)

    def stop(self) -> None:
        """Stop the webhook update service."""
        super().stop()

        # Shutdown Flask server
        if self.server_thread and self.server_thread.is_alive():
            # No clean way to stop Flask in a thread, so we'll just wait for it to terminate
            self.server_thread.join(timeout=5.0)

        logger.info(f"Stopped GitLab webhook service for tracker {self.tracker.id}")

    def update(self) -> int:
        """
        Process updates for the tracker.

        Since we're using webhooks, this is a no-op for this service.

        Returns:
            Number of issues updated (always 0 for webhooks)
        """
        # No polling updates needed for webhook service
        return 0
