"""
Synchronizes subscription plans from a YAML file to the database and Stripe.

This script reads the `plans.yaml` file, connects to the Stripe API to create
or update corresponding products and prices, and then updates the `Plan` table
in the SpaceBridge database with the plan details and Stripe IDs.
"""

import os
import sys
import yaml
import stripe

from spacebridge.config import settings
from spacemodels.models import Plan
from spacemodels.db.session import get_db_session

# Add the project root to the Python path to allow for module imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)

# --- Configuration ---
STRIPE_API_KEY = settings.stripe_secret_key
DATABASE_URL = settings.database.url
PLANS_FILE_PATH = os.path.join(project_root, "plans.yaml")


def sync_plans():
    """
    Main function to orchestrate the synchronization of plans.
    """
    print("Starting plan synchronization...")

    # 1. Configure Stripe API
    stripe.api_key = STRIPE_API_KEY
    print("Stripe API key configured.")

    # 2. Load plans from YAML file
    try:
        with open(PLANS_FILE_PATH, "r") as f:
            plans_data = yaml.safe_load(f).get("plans", [])
        print(f"Loaded {len(plans_data)} plans from {PLANS_FILE_PATH}.")
    except FileNotFoundError:
        print(f"ERROR: Plans file not found at {PLANS_FILE_PATH}")
        return
    except Exception as e:
        print(f"ERROR: Failed to read or parse YAML file: {e}")
        return

    # 3. Connect to the database
    try:
        db = next(get_db_session())
        print("Successfully connected to the database.")
    except Exception as e:
        print(f"ERROR: Could not connect to the database: {e}")
        return

    # 4. Process each plan
    for plan in plans_data:
        process_plan(plan, db)

    print("\nPlan synchronization completed successfully.")


def process_plan(plan_details: dict, db):
    """
    Processes a single plan: syncs with Stripe (if paid) and the database.
    """
    plan_id = plan_details["id"]
    print(f"\n--- Processing plan: {plan_id} ---")

    is_free_plan = (
        plan_details.get("price_monthly", 0) == 0
        and plan_details.get("price_annually", 0) == 0
    )
    stripe_product_id = None

    if not is_free_plan:
        try:
            # Step 1: Create or retrieve the Product in Stripe
            product = None
            try:
                product = stripe.Product.retrieve(plan_id)
                print(f"Retrieved existing Stripe Product: {product.id}")
            except stripe.error.InvalidRequestError:
                product = stripe.Product.create(id=plan_id, name=plan_details["name"])
                print(f"Created new Stripe Product: {product.id}")
            stripe_product_id = product.id

            # Step 2: Idempotently update prices in Stripe
            def update_price(interval: str, amount: float):
                lookup_key = f"{plan_id}_{interval}"
                new_price_in_cents = int(amount * 100)

                existing_prices = stripe.Price.list(
                    lookup_keys=[lookup_key], active=True
                ).data

                found_matching_price = False
                prices_to_deactivate = []

                for price in existing_prices:
                    if price.unit_amount == new_price_in_cents:
                        found_matching_price = True
                    else:
                        prices_to_deactivate.append(price.id)

                if found_matching_price:
                    print(f"Price for {lookup_key} is already up to date.")
                    # Deactivate any other non-matching prices for this key
                    for price_id in prices_to_deactivate:
                        stripe.Price.modify(price_id, active=False)
                        print(
                            f"Deactivated redundant old price {price_id} for {lookup_key}."
                        )
                else:
                    # No matching price found, so deactivate all old ones and create a new one.
                    for price_id in prices_to_deactivate:
                        stripe.Price.modify(price_id, active=False)
                        print(f"Deactivated old price {price_id} for {lookup_key}.")

                    stripe.Price.create(
                        product=product.id,
                        unit_amount=new_price_in_cents,
                        currency="usd",
                        recurring={"interval": interval},
                        lookup_key=lookup_key,
                    )
                    print(f"Created new {interval} price for {plan_id}.")

            if plan_details.get("price_monthly") is not None:
                update_price("month", plan_details["price_monthly"])
            if plan_details.get("price_annually") is not None:
                update_price("year", plan_details["price_annually"])

        except Exception as e:
            print(f"ERROR processing Stripe objects for plan {plan_id}: {e}")
            return  # Stop processing this plan if Stripe fails

    else:
        print(f"Plan '{plan_id}' is a free plan. Skipping Stripe synchronization.")

    # Step 3: Create or update the Plan in the database
    try:
        db_plan = db.query(Plan).filter(Plan.id == plan_id).first()
        plan_data = {
            "name": plan_details["name"],
            "price_monthly": plan_details["price_monthly"],
            "price_annually": plan_details["price_annually"],
            "features": plan_details["features"],
            "stripe_product_id": stripe_product_id,
        }
        if db_plan:
            print(f"Updating existing DB plan: {plan_id}")
            for key, value in plan_data.items():
                setattr(db_plan, key, value)
        else:
            print(f"Creating new DB plan: {plan_id}")
            db_plan = Plan(id=plan_id, **plan_data)
            db.add(db_plan)

        db.commit()
        print(f"Successfully synced plan '{plan_id}' to the database.")

    except Exception as e:
        print(f"ERROR updating database for plan {plan_id}: {e}")
        db.rollback()

    print(f"--- Finished processing plan: {plan_id} ---")


if __name__ == "__main__":
    sync_plans()
