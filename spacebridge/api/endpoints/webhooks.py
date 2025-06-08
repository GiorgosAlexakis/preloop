import hashlib
import hmac
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session, joinedload

from spacemodels.crud.organization import CRUDOrganization
from spacemodels.models.organization import Organization  # Added
from spacemodels.crud.tracker import CRUDTracker
from spacemodels.models.tracker import Tracker
from spacemodels.db.session import get_db_session

logger = logging.getLogger(__name__)

router = APIRouter()

# Default subscribed events if not configured on the tracker
DEFAULT_GITHUB_SUBSCRIBED_EVENTS = [
    "push",
    "issues",
    "issue_comment",
    "pull_request",
    "release",
    "deployment_status",
]
DEFAULT_GITLAB_SUBSCRIBED_EVENTS = [
    "push_events",
    "issues_events",
    "merge_requests_events",
    "note_events",
    "pipeline_events",
    "job_events",
    "releases_events",
]
DEFAULT_JIRA_SUBSCRIBED_EVENTS = [
    "jira:issue_created",
    "jira:issue_updated",
    "jira:issue_deleted",
    "comment_created",
    "comment_updated",
    "comment_deleted",
    "worklog_created",
    "worklog_updated",
    "worklog_deleted",
]


@router.post("/private/webhooks/{tracker_type}/{identifier_in_url}")
async def receive_webhook(
    tracker_type: str,
    identifier_in_url: str,
    request: Request,
    db: Session = Depends(get_db_session),
):
    """
    Receive webhook events from external trackers (GitHub, GitLab).

    Parses the payload to identify the organization and updates its
    last_webhook_update timestamp.
    """
    logger.info(
        f"Received webhook for tracker_type={tracker_type}, identifier_in_url={identifier_in_url}"
    )

    # --- 1. Read Raw Body ---
    raw_body = await request.body()
    logger.debug(f"Raw webhook body length: {len(raw_body)}")

    # --- 2. Resolve Tracker, Secret, and context for timestamp update ---
    resolved_tracker: Optional[Tracker] = None
    webhook_secret_to_use: Optional[str] = None
    organization_context_for_timestamp: Optional[CRUDOrganization.model] = None
    default_event_list_for_type: List[str] = []
    event_type_header_key: Optional[str] = None

    if tracker_type.lower() in ["github", "gitlab"]:
        # Use the direct Organization model for querying and joinedload
        organization_data = (
            db.query(Organization)
            .options(joinedload(Organization.tracker))
            .filter(Organization.identifier == identifier_in_url)
            .first()
        )

        if not organization_data:
            logger.warning(
                f"Organization not found for identifier={identifier_in_url}, tracker_type={tracker_type}"
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found"
            )

        if not organization_data.tracker:
            logger.error(
                f"Tracker not found for organization ID {organization_data.id}, identifier {identifier_in_url}"
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Tracker configuration error",
            )

        if not organization_data.webhook_secret:  # For GH/GL, secret is on Org model
            logger.error(
                f"Webhook secret not configured for organization ID {organization_data.id}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Webhook not configured correctly",
            )

        resolved_tracker = organization_data.tracker
        webhook_secret_to_use = organization_data.webhook_secret
        organization_context_for_timestamp = (
            organization_data  # Use the fetched organization data
        )
        if tracker_type.lower() == "github":
            default_event_list_for_type = DEFAULT_GITHUB_SUBSCRIBED_EVENTS
            event_type_header_key = "X-GitHub-Event"
        else:  # gitlab
            default_event_list_for_type = DEFAULT_GITLAB_SUBSCRIBED_EVENTS
            event_type_header_key = "X-Gitlab-Event"

    elif tracker_type.lower() == "jira":
        # For Jira, identifier_in_url is the Tracker.id
        crud_tracker_instance = CRUDTracker(db)  # CRUD helper needs db session
        # Fetch tracker ensuring it's a Jira tracker
        tracker_candidate = (
            db.query(Tracker)
            .filter(Tracker.id == identifier_in_url, Tracker.tracker_type == "jira")
            .first()
        )

        if not tracker_candidate:
            logger.warning(
                f"Jira Tracker not found or type mismatch for id={identifier_in_url}"
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Jira Tracker not found"
            )

        resolved_tracker = tracker_candidate

        if (
            not resolved_tracker.jira_webhook_secret
        ):  # New field on Tracker model for Jira
            logger.error(
                f"Jira webhook secret not configured for Tracker ID {resolved_tracker.id}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Jira webhook not configured correctly",
            )

        webhook_secret_to_use = resolved_tracker.jira_webhook_secret
        default_event_list_for_type = DEFAULT_JIRA_SUBSCRIBED_EVENTS
        # Event type for Jira is in payload ("webhookEvent"), not a header.

    else:
        logger.error(f"Unsupported tracker_type for webhook: {tracker_type}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported tracker_type: {tracker_type}",
        )

    if not resolved_tracker:  # Should have been caught above
        logger.error(
            f"Failed to resolve tracker for {tracker_type} with identifier {identifier_in_url}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error resolving tracker.",
        )

    if not resolved_tracker.is_active:
        logger.warning(
            f"Webhook received for inactive tracker ID {resolved_tracker.id} ({tracker_type}). Ignoring."
        )
        # Return 200 OK to not cause retries from Jira/GitHub/GitLab for an intentionally inactive tracker
        return {"status": "ignored", "message": "Tracker is inactive"}

    if webhook_secret_to_use is None:  # Should also be caught
        logger.error(f"Webhook secret is not set for tracker ID {resolved_tracker.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook secret configuration error.",
        )

    # --- 3. Verify Signature ---
    encoded_secret = webhook_secret_to_use.encode("utf-8")

    if tracker_type.lower() == "github":
        signature_header = request.headers.get("X-Hub-Signature-256")
        if not signature_header:
            logger.warning("Missing X-Hub-Signature-256 header for GitHub webhook")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Missing GitHub signature"
            )
        try:
            method, signature_hash = signature_header.split("=", 1)
            if method.lower() != "sha256":
                logger.warning(f"Unsupported GitHub signature method: {method}")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Unsupported GitHub signature method",
                )

            expected_signature = hmac.new(
                encoded_secret, raw_body, hashlib.sha256
            ).hexdigest()

            if not hmac.compare_digest(signature_hash, expected_signature):
                logger.warning(
                    f"GitHub webhook signature mismatch for tracker ID {resolved_tracker.id}"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Invalid GitHub signature",
                )
            logger.info(
                f"GitHub webhook signature verified successfully for tracker ID {resolved_tracker.id}"
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error during GitHub signature verification: {e}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="GitHub signature verification failed",
            )

    elif tracker_type.lower() == "gitlab":
        token_header = request.headers.get("X-Gitlab-Token")
        if not token_header:
            logger.warning("Missing X-Gitlab-Token header for GitLab webhook")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Missing GitLab token"
            )

        # Use compare_digest for timing attack resistance
        if not hmac.compare_digest(
            token_header.encode("utf-8"), encoded_secret
        ):  # Use encoded_secret
            logger.warning(
                f"GitLab webhook token mismatch for tracker ID {resolved_tracker.id}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Invalid GitLab token"
            )
        logger.info(
            f"GitLab webhook token verified successfully for tracker ID {resolved_tracker.id}"
        )

    elif tracker_type.lower() == "jira":
        # Jira Cloud webhooks use HMAC-SHA256 signature with a pre-configured secret.
        # The signature is in the 'X-Atlassian-Signature' header, format: 'sha256=<signature>'
        signature_header = request.headers.get("X-Atlassian-Signature")
        if not signature_header:
            logger.warning(
                f"Missing X-Atlassian-Signature header for Jira webhook, tracker ID {resolved_tracker.id}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Missing Jira signature"
            )

        try:
            method, signature_hash = signature_header.split("=", 1)
            if method.lower() != "sha256":
                logger.warning(
                    f"Unsupported Jira signature method: {method} for tracker ID {resolved_tracker.id}"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Unsupported Jira signature method",
                )

            expected_signature = hmac.new(
                encoded_secret, raw_body, hashlib.sha256
            ).hexdigest()

            if not hmac.compare_digest(signature_hash, expected_signature):
                logger.warning(
                    f"Jira webhook signature mismatch for tracker ID {resolved_tracker.id}"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Invalid Jira signature",
                )
            logger.info(
                f"Jira webhook signature verified successfully for tracker ID {resolved_tracker.id}"
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(
                f"Error during Jira signature verification for tracker ID {resolved_tracker.id}: {e}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Jira signature verification failed",
            )
    # Note: No 'else' here as unsupported tracker_types are handled during tracker resolution.

    # --- 4. Parse Payload & Determine Event Type ---
    actual_event_type: Optional[str] = None
    parsed_payload: Dict[str, Any]

    try:
        parsed_payload = await request.json()
    except Exception as e:
        logger.error(
            f"Failed to parse webhook JSON payload for tracker ID {resolved_tracker.id}: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON payload"
        )

    if tracker_type.lower() in ["github", "gitlab"]:
        if not event_type_header_key:  # Should be set during tracker resolution
            logger.error(
                f"Internal error: event_type_header_key not set for {tracker_type}"
            )
            raise HTTPException(
                status_code=500, detail="Internal configuration error for event type."
            )
        actual_event_type = request.headers.get(event_type_header_key)
        if not actual_event_type:
            logger.warning(
                f"Could not determine event type from header '{event_type_header_key}' for {tracker_type}, tracker ID {resolved_tracker.id}."
            )
            # Allow to proceed, subscription check might still pass if default allows all or if subscribed_events is empty.
    elif tracker_type.lower() == "jira":
        actual_event_type = parsed_payload.get("webhookEvent")
        if not actual_event_type:
            logger.warning(
                f"Jira webhook missing 'webhookEvent' in payload for tracker ID {resolved_tracker.id}."
            )
            # If no event type, it cannot match a specific subscription.
            # If default is to allow all, this might be an issue. For now, treat as unmatchable if specific subs exist.
            # Consider raising 400 if event type is strictly required.
            # For now, if it's None, it won't match any specific event in subscribed_events.

    # --- 5. Check Subscription ---
    subscribed_events_for_tracker = resolved_tracker.subscribed_events

    # Determine effective list of subscribed events
    if (
        subscribed_events_for_tracker is None or not subscribed_events_for_tracker
    ):  # Catches None or empty list
        effective_subscribed_events = default_event_list_for_type
        logger.debug(
            f"Tracker ID {resolved_tracker.id} has no specific subscriptions, using defaults for {tracker_type}: {default_event_list_for_type}"
        )
    else:
        effective_subscribed_events = subscribed_events_for_tracker
        logger.debug(
            f"Tracker ID {resolved_tracker.id} subscribed to: {effective_subscribed_events}"
        )

    if not actual_event_type or actual_event_type not in effective_subscribed_events:
        # Handles cases where actual_event_type is None (e.g. missing Jira 'webhookEvent' or GH/GL header)
        # or if the event is simply not in the list.
        log_msg_event_type = (
            actual_event_type if actual_event_type else "Unknown/Missing"
        )
        logger.info(
            f"Event '{log_msg_event_type}' for tracker ID {resolved_tracker.id} ({tracker_type}) is not in the subscribed list ({effective_subscribed_events}). Skipping NATS publish."
        )
        # Still update timestamp as the webhook was validly received and authenticated (if applicable)
        try:
            if organization_context_for_timestamp:  # GH/GL
                organization_context_for_timestamp.last_webhook_update = datetime.now(
                    timezone.utc
                )
                db.add(organization_context_for_timestamp)
            else:  # Jira or other direct tracker updates
                resolved_tracker.last_updated = datetime.now(timezone.utc)
                db.add(resolved_tracker)
            db.commit()
        except Exception as e_ts:
            db.rollback()
            logger.error(
                f"Failed to update timestamp after skipping non-subscribed event for tracker {resolved_tracker.id}: {e_ts}"
            )
        return {
            "status": "success",
            "message": "Event not subscribed",
            "tracker_id": resolved_tracker.id,
        }

    logger.info(
        f"Event '{actual_event_type}' for tracker ID {resolved_tracker.id} ({tracker_type}) IS SUBSCRIBED. Proceeding."
    )

    # --- 6. Publish to NATS (Simulated) ---
    logger.debug(
        f"Webhook payload for subscribed event (tracker ID {resolved_tracker.id}): {parsed_payload}"
    )
    # TODO: Add more sophisticated payload validation/parsing based on tracker_type
    # TODO: Publish the validated 'actual_event_type' and 'parsed_payload' to NATS here.
    logger.info(
        f"SIMULATING NATS PUBLISH: Event Type: {actual_event_type}, Tracker Type: {tracker_type}, TrackerID: {resolved_tracker.id}"
    )

    # --- 7. Update Timestamp (after successful processing) ---
    try:
        if organization_context_for_timestamp:  # GH/GL
            organization_context_for_timestamp.last_webhook_update = datetime.now(
                timezone.utc
            )
            db.add(organization_context_for_timestamp)
            logger.info(
                f"Updated last_webhook_update for organization ID {organization_context_for_timestamp.id}"
            )
        elif resolved_tracker:  # Jira
            resolved_tracker.last_updated = datetime.now(
                timezone.utc
            )  # Use the general last_updated
            db.add(resolved_tracker)
            logger.info(f"Updated last_updated for tracker ID {resolved_tracker.id}")
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(
            f"Failed to update timestamp for tracker {resolved_tracker.id} / org: {e}"
        )
        # Don't fail the whole request if only timestamp update fails after processing
        # but log it as a high priority issue.
        # Consider if this should be a 500 error. For now, let request succeed if NATS part was okay.

    return {"status": "success", "tracker_id": resolved_tracker.id}
