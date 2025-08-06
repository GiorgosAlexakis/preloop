"""
API endpoints for billing, subscriptions, and plans.
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from spacebridge.api.auth.jwt import get_current_active_user
from spacemodels.models import Account
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
def list_plans(service: BillingService = Depends(get_billing_service)):
    """
    List all available subscription plans.
    """
    return service.db.query(Plan).filter(Plan.is_active).all()


@router.get("/subscription", response_model=Subscription)
def get_subscription(
    service: BillingService = Depends(get_billing_service),
    current_user: Account = Depends(get_current_active_user),
):
    """
    Get the current user's subscription details.
    """
    subscription = (
        service.db.query(Subscription)
        .filter(Subscription.account_id == current_user.id)
        .first()
    )
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    return subscription
