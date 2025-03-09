# /workspace/shiftwise/subscriptions/utils.py

import logging
from datetime import datetime, timezone as datetime_timezone

from django.conf import settings
import stripe

from .models import Subscription, Plan

logger = logging.getLogger(__name__)

# Initialize Stripe with the secret key from settings
stripe.api_key = settings.STRIPE_SECRET_KEY


def create_stripe_customer(agency):
    """
    Creates a Stripe customer for the given agency.
    If a customer with the same email exists, returns the existing customer.
    """
    try:
        # Search for existing customer by email
        customers = stripe.Customer.list(email=agency.email, limit=1)
        if customers.data:
            customer = customers.data[0]
            logger.info(
                f"Existing Stripe customer found: {customer.id} for agency: {agency.name}"
            )
            return customer

        # Create new customer if none exists
        customer = stripe.Customer.create(
            name=agency.name,
            email=agency.email,
            metadata={
                "agency_id": agency.id,
            },
        )
        logger.info(f"Stripe customer created: {customer.id} for agency: {agency.name}")
        return customer
    except stripe.error.StripeError as e:
        logger.exception(f"Stripe error while creating customer: {e}")
        raise
    except Exception as e:
        logger.exception(f"Unexpected error while creating Stripe customer: {e}")
        raise


def update_subscription_from_stripe(agency, stripe_sub):
    """
    Update or create a local Subscription record from the given Stripe subscription data.
    Returns the Subscription if successful, or None if the Plan is not found.
    """
    plan_id = stripe_sub["items"]["data"][0]["price"]["id"]

    # Attempt to find the matching Plan in the database
    try:
        plan = Plan.objects.get(stripe_price_id=plan_id)
    except Plan.DoesNotExist:
        logger.error(
            f"Plan with price ID {plan_id} not found. Unable to update subscription for {agency.name}."
        )
        return None

    # Convert Stripe timestamps to Python datetime
    current_period_start = datetime.fromtimestamp(
        stripe_sub["current_period_start"], tz=datetime_timezone.utc
    )
    current_period_end = datetime.fromtimestamp(
        stripe_sub["current_period_end"], tz=datetime_timezone.utc
    )

    # Update or create the local Subscription
    subscription, created = Subscription.objects.update_or_create(
        agency=agency,
        defaults={
            "plan": plan,
            "stripe_subscription_id": stripe_sub.id,
            "is_active": (stripe_sub.status == "active"),
            "status": stripe_sub.status,
            "current_period_start": current_period_start,
            "current_period_end": current_period_end,
            "is_expired": False,
        },
    )

    logger.info(
        f"{'Created' if created else 'Updated'} subscription for {agency.name} from Stripe data"
    )
    return subscription