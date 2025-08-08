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
from spacemodels.models import Account
from spacemodels.models.plan import Plan as PlanModel, Subscription as SubscriptionModel
from spacemodels.schemas.plan import Plan, PlanCreate, Subscription
from spacebridge.services.billing import BillingService
from spacemodels.db.session import get_db_session

router = APIRouter()


def get_billing_service(db: Session = Depends(get_db_session)) -> BillingService:
    """Dependency to get the billing service."""
    return BillingService(db)


@router.post("/plans", response_model=Plan, status_code=201)
def create_plan(
    plan: PlanCreate,
    service: BillingService = Depends(get_billing_service),
    current_user: Account = Depends(get_current_active_user),
):
    """
    Create a new subscription plan.
    (Requires superuser privileges).
    """
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized")
    return service.create_plan(plan)


@router.get("/plans", response_model=List[Plan])
def list_public_plans(service: BillingService = Depends(get_billing_service)):
    """
    List all available public subscription plans.
    """
    return (
        service.db.query(PlanModel)
        .filter(PlanModel.is_active, PlanModel.is_custom.is_(False))
        .order_by(PlanModel.created_at.asc())
        .all()
    )


@router.get("/custom-plans", response_model=List[Plan])
def list_custom_plans(
    service: BillingService = Depends(get_billing_service),
    current_user: Account = Depends(get_current_active_user),
):
    """
    List custom subscription plans for the current user's account.
    """
    return (
        service.db.query(PlanModel)
        .filter(
            PlanModel.is_active,
            PlanModel.is_custom,
            PlanModel.account_id == current_user.id,
        )
        .all()
    )


@router.get("/subscription", response_model=Subscription)
def get_subscription(
    service: BillingService = Depends(get_billing_service),
    current_user: Account = Depends(get_current_active_user),
):
    """
    Get the current user's subscription details.
    """
    subscription = (
        service.db.query(SubscriptionModel)
        .filter(SubscriptionModel.account_id == current_user.id)
        .order_by(SubscriptionModel.created_at.desc())
        .first()
    )
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    return subscription


@router.get("/checkout-success")
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
    if account.hashed_password == "NEEDS_RESET":
        params = {
            "username": account.username,
            "email": account.email,
            "full_name": account.full_name or "",
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


@router.get("/checkout-session-details", response_model=CheckoutSessionDetailsResponse)
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


@router.post("/create-checkout-session")  # No response model, as it can vary
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

    account_id = current_user.id if current_user else None
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


@router.post("/create-portal-session", response_model=CreatePortalSessionResponse)
def create_portal_session(
    request: CreatePortalSessionRequest,
    service: BillingService = Depends(get_billing_service),
    current_user: Account = Depends(get_current_active_user),
):
    """Create a Stripe Customer Portal session."""
    try:
        url = service.create_portal_session(
            account_id=current_user.id, return_url=request.return_url
        )
        return CreatePortalSessionResponse(url=url)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/webhooks")
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


@router.post("/sync-subscription", status_code=200)
def sync_subscription(
    service: BillingService = Depends(get_billing_service),
    current_user: Account = Depends(get_current_active_user),
):
    """Synchronizes the user's subscription status from Stripe to the local database."""
    try:
        service.sync_subscription_status(account_id=current_user.id)
        return {"status": "success"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
