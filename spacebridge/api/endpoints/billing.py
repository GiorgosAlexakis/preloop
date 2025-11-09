"""
API endpoints for billing, subscriptions, and plans.
"""

import urllib.parse

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Header
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from spacebridge.api.auth.jwt import (
    get_user_from_token_if_valid,
    get_current_active_user,
)
from spacemodels.models.user import User
from spacemodels.schemas.plan import Plan, PlanCreate, Subscription
from spacebridge.services.billing import BillingService
from spacemodels.db.session import get_db_session
from spacemodels.crud.plan import plan as crud_plan, subscription as crud_subscription

router = APIRouter()


def get_billing_service(db: Session = Depends(get_db_session)) -> BillingService:
    """Dependency to get the billing service."""
    return BillingService(db)


@router.post("/billing/plans", response_model=Plan, status_code=201)
def create_plan(
    plan: PlanCreate,
    service: BillingService = Depends(get_billing_service),
    current_user: User = Depends(get_current_active_user),
):
    """
    Create a new subscription plan.
    (Requires superuser privileges).
    """
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized")
    return service.create_plan(plan)


@router.get("/billing/plans", response_model=List[Plan])
def list_public_plans(service: BillingService = Depends(get_billing_service)):
    """
    List all available public subscription plans.
    """
    return crud_plan.get_active_public_plans(service.db)


@router.get("/billing/custom-plans", response_model=List[Plan])
def list_custom_plans(
    service: BillingService = Depends(get_billing_service),
    current_user: User = Depends(get_current_active_user),
):
    """
    List custom subscription plans for the current user's account.
    """
    return crud_plan.get_active_custom_plans_for_account(
        service.db, account_id=current_user.account_id
    )


@router.get("/billing/subscription", response_model=Subscription)
def get_subscription(
    service: BillingService = Depends(get_billing_service),
    current_user: User = Depends(get_current_active_user),
):
    """
    Get the current user's subscription details.
    """
    subscription = crud_subscription.get_latest_for_account(
        service.db, account_id=current_user.account_id
    )
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    return subscription


@router.get("/billing/checkout-success")
def checkout_success(
    session_id: str,
    service: BillingService = Depends(get_billing_service),
):
    """
    Handles the synchronous part of a successful checkout.
    Processes the session, creates the user, and redirects to the welcome page.
    """
    account = service._handle_checkout_session_completed(session_id)
    if not account:
        raise HTTPException(
            status_code=404, detail="Could not process checkout session."
        )

    # For new users, redirect to the welcome page with their details.
    # For existing users, redirect them to the console.
    # Get the primary user for the account
    from spacemodels.crud import crud_user

    db: Session = next(get_db_session())
    primary_user = None
    if account.primary_user_id:
        primary_user = crud_user.get(db, id=str(account.primary_user_id))

    if primary_user and primary_user.hashed_password == "NEEDS_RESET":
        params = {
            "username": primary_user.username,
            "email": primary_user.email,
            "full_name": primary_user.full_name or "",
        }
        redirect_url = f"/welcome?{urllib.parse.urlencode(params)}"
    else:
        # This is an existing user, we should log them in and send them to the console.
        # For simplicity in this step, we'll just send them to the login page.
        # A more advanced implementation would create a login token here.
        redirect_url = "/console/settings/subscription?message=subscription_updated"

    return RedirectResponse(url=redirect_url)


class CheckoutSessionDetailsResponse(BaseModel):
    email: str
    username: str


@router.get(
    "/billing/checkout-session-details", response_model=CheckoutSessionDetailsResponse
)
def get_checkout_session_details(
    session_id: str,
    service: BillingService = Depends(get_billing_service),
):
    """
    Retrieve user details from a completed checkout session.
    This is used by the onboarding/welcome page.
    """
    try:
        details = service.get_user_details_from_session(session_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    if not details:
        raise HTTPException(
            status_code=404, detail="Session not found or not completed."
        )
    return details


class CreateCheckoutSessionRequest(BaseModel):
    plan_id: str
    interval: str  # 'month' or 'year'


class CreateCheckoutSessionResponse(BaseModel):
    url: str


@router.post("/billing/create-checkout-session")  # No response model, as it can vary
async def create_checkout_session(
    request: CreateCheckoutSessionRequest,
    service: BillingService = Depends(get_billing_service),
    db: Session = Depends(get_db_session),
    authorization: Optional[str] = Header(None),
):
    """
    Creates a Stripe Checkout session for new subscriptions, or directly
    updates the subscription for existing customers.
    """
    current_user = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split("Bearer ")[1]
        current_user = await get_user_from_token_if_valid(token, db)

    account_id = current_user.account_id if current_user else None
    result = service.create_checkout_session(
        plan_id=request.plan_id,
        interval=request.interval,
        account_id=account_id,
    )
    return result


class CreatePortalSessionRequest(BaseModel):
    return_url: str


class CreatePortalSessionResponse(BaseModel):
    url: str


@router.post(
    "/billing/create-portal-session", response_model=CreatePortalSessionResponse
)
def create_portal_session(
    request: CreatePortalSessionRequest,
    service: BillingService = Depends(get_billing_service),
    current_user: User = Depends(get_current_active_user),
):
    """Create a Stripe Customer Portal session."""
    import logging
    import traceback

    logger = logging.getLogger(__name__)

    try:
        logger.info(f"Creating portal session for account {current_user.account_id}")
        url = service.create_portal_session(
            account_id=current_user.account_id, return_url=request.return_url
        )
        logger.info("Portal session created successfully")
        return CreatePortalSessionResponse(url=url)
    except Exception as e:
        logger.error(f"Error creating portal session: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/billing/webhooks")
async def stripe_webhooks(
    request: Request, service: BillingService = Depends(get_billing_service)
):
    """Handle incoming Stripe webhooks."""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    try:
        service.handle_webhook(payload, sig_header)
        return {"status": "success"}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/billing/sync-subscription", status_code=200)
def sync_subscription(
    service: BillingService = Depends(get_billing_service),
    current_user: User = Depends(get_current_active_user),
):
    """Synchronizes the user's subscription status from Stripe to the local database."""
    try:
        service.sync_subscription_status(account_id=current_user.account_id)
        return {"status": "success"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
