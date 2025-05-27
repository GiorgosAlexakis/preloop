import hashlib
import hmac
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from spacemodels.crud.organization import CRUDOrganization
from spacemodels.db.session import get_db_session

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/private/webhooks/{tracker_type}/{org_identifier}")
async def receive_webhook(
    tracker_type: str,
    org_identifier: str,
    request: Request,
    db: Session = Depends(get_db_session),
):
    """
    Receive webhook events from external trackers (GitHub, GitLab).

    Parses the payload to identify the organization and updates its
    last_webhook_update timestamp.
    """
    logger.info(
        f"Received webhook for tracker_type={tracker_type}, org_identifier={org_identifier}"
    )

    # --- 1. Read Raw Body ---
    raw_body = await request.body()
    logger.debug(f"Raw webhook body length: {len(raw_body)}")

    # --- 2. Find Organization and Secret ---
    crud_org = CRUDOrganization()
    organization = crud_org.get_by_identifier(db=db, identifier=org_identifier)

    if not organization:
        logger.warning(
            f"Organization not found for identifier={org_identifier}, tracker_type={tracker_type}"
        )
        # Use 403 to avoid leaking information about existing orgs
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Invalid request"
        )

    if not organization.webhook_secret:
        logger.error(
            f"Webhook secret not configured for organization ID {organization.id}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Webhook not configured correctly",
        )

    # --- 3. Verify Signature ---
    secret = organization.webhook_secret.encode("utf-8")

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

            expected_signature = hmac.new(secret, raw_body, hashlib.sha256).hexdigest()

            if not hmac.compare_digest(signature_hash, expected_signature):
                logger.warning("GitHub webhook signature mismatch")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Invalid GitHub signature",
                )
            logger.info(
                f"GitHub webhook signature verified successfully for org ID {organization.id}"
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
        if not hmac.compare_digest(token_header.encode("utf-8"), secret):
            logger.warning("GitLab webhook token mismatch")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Invalid GitLab token"
            )
        logger.info(
            f"GitLab webhook token verified successfully for org ID {organization.id}"
        )

    else:
        logger.error(
            f"Unsupported tracker type for webhook verification: {tracker_type}"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Webhook verification not supported for tracker type: {tracker_type}",
        )

    # --- 4. Parse Payload (only after verification) ---
    try:
        payload = await request.json()
        logger.debug(f"Webhook payload: {payload}")
        # TODO: Add more sophisticated payload validation/parsing based on tracker_type
    except Exception as e:
        logger.error(f"Failed to parse webhook payload after verification: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON payload"
        )

    # --- 5. Update Timestamp ---
    try:
        organization.last_webhook_update = datetime.now(timezone.utc)
        db.add(organization)  # Ensure changes are staged for commit
        db.commit()
        logger.info(
            f"Updated last_webhook_update for organization ID {organization.id}"
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update organization {organization.id} timestamp: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update organization timestamp",
        )

    return {"status": "success", "organization_id": organization.id}
