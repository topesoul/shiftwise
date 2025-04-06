# /workspace/shiftwise/subscriptions/management/commands/debug_subscription.py

import logging

import stripe

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import Agency
from subscriptions.models import Subscription

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Debug subscription issues for a specific agency"

    def add_arguments(self, parser):
        parser.add_argument(
            "agency_id",
            type=int,
            help="Agency ID to debug",
        )
        parser.add_argument(
            "--fix",
            action="store_true",
            help="Fix issues automatically",
        )

    def handle(self, *args, **options):
        stripe.api_key = settings.STRIPE_SECRET_KEY
        agency_id = options["agency_id"]
        fix_mode = options.get("fix", False)

        try:
            agency = Agency.objects.get(id=agency_id)
        except Agency.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"Agency with ID {agency_id} not found"))
            return

        self.stdout.write(f"Debugging subscription for: {agency.name} (ID: {agency.id})")

        # Step 1: Check customer ID
        customer_id = agency.stripe_customer_id
        self.stdout.write(f"Stripe Customer ID: {customer_id or 'Not set'}")

        customer_valid = False
        if customer_id:
            try:
                customer = stripe.Customer.retrieve(customer_id)
                self.stdout.write(self.style.SUCCESS(f"Stripe Customer exists: {customer.email}"))
                customer_valid = True
            except stripe.error.InvalidRequestError:
                self.stdout.write(self.style.ERROR("Stripe Customer ID is invalid"))
                if fix_mode:
                    try:
                        from subscriptions.utils import create_stripe_customer

                        customer = create_stripe_customer(agency)
                        agency.stripe_customer_id = customer.id
                        agency.save(update_fields=["stripe_customer_id"])
                        self.stdout.write(
                            self.style.SUCCESS(f"Created new Stripe customer: {customer.id}")
                        )
                        customer_valid = True
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"Failed to create customer: {e}"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error retrieving customer: {e}"))
        else:
            self.stdout.write(self.style.ERROR("No Stripe Customer ID set"))
            if fix_mode:
                try:
                    from subscriptions.utils import create_stripe_customer

                    customer = create_stripe_customer(agency)
                    agency.stripe_customer_id = customer.id
                    agency.save(update_fields=["stripe_customer_id"])
                    self.stdout.write(self.style.SUCCESS(f"Created Stripe customer: {customer.id}"))
                    customer_valid = True
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"Failed to create customer: {e}"))

        # Step 2: Check local subscription
        self.stdout.write("\nChecking local subscription records:")
        try:
            subscriptions = Subscription.objects.filter(agency=agency)
            if not subscriptions.exists():
                self.stdout.write(self.style.WARNING("No local subscription records found"))
            else:
                self.stdout.write(f"Found {subscriptions.count()} local subscription records:")

                for idx, sub in enumerate(subscriptions, 1):
                    self.stdout.write(f"\nSubscription #{idx}:")
                    self.stdout.write(f"  ID: {sub.id}")
                    self.stdout.write(f"  Plan: {sub.plan.name} ({sub.plan.billing_cycle})")
                    self.stdout.write(f"  Is Active: {sub.is_active}")
                    self.stdout.write(f"  Status: {sub.status}")
                    self.stdout.write(f"  Stripe Sub ID: {sub.stripe_subscription_id or 'Not set'}")
                    self.stdout.write(f"  Current Period End: {sub.current_period_end}")

                    now = timezone.now()
                    if sub.current_period_end and sub.current_period_end < now and sub.is_active:
                        self.stdout.write(
                            self.style.ERROR(
                                "  Subscription period has ended but is still marked active"
                            )
                        )
                        if fix_mode:
                            sub.is_active = False
                            sub.is_expired = True
                            sub.status = "canceled"
                            sub.save()
                            self.stdout.write(
                                self.style.SUCCESS("  Fixed: Marked as inactive and expired")
                            )

                    # Verify Stripe subscription if ID exists
                    if sub.stripe_subscription_id and customer_valid:
                        try:
                            stripe_sub = stripe.Subscription.retrieve(sub.stripe_subscription_id)
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f"  Stripe subscription exists: {stripe_sub.status}"
                                )
                            )

                            # Check for status mismatch
                            stripe_active = stripe_sub.status == "active"
                            if sub.is_active != stripe_active:
                                self.stdout.write(
                                    self.style.ERROR(
                                        f"  Status mismatch: Local={sub.is_active}, Stripe={stripe_active}"
                                    )
                                )
                                if fix_mode:
                                    sub.is_active = stripe_active
                                    sub.status = stripe_sub.status
                                    sub.save()
                                    self.stdout.write(
                                        self.style.SUCCESS(
                                            f"  Fixed: Updated status to match Stripe"
                                        )
                                    )

                        except stripe.error.InvalidRequestError:
                            self.stdout.write(
                                self.style.ERROR("  Stripe subscription ID is invalid")
                            )
                            if fix_mode and sub.is_active:
                                sub.is_active = False
                                sub.status = "canceled"
                                sub.save()
                                self.stdout.write(self.style.SUCCESS("  Fixed: Marked as inactive"))
                        except Exception as e:
                            self.stdout.write(
                                self.style.ERROR(f"  Error retrieving Stripe subscription: {e}")
                            )

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error checking local subscriptions: {e}"))

        # Step 3: Check Stripe subscriptions if customer is valid
        if customer_valid:
            self.stdout.write("\nChecking Stripe subscriptions:")
            try:
                stripe_subs = stripe.Subscription.list(
                    customer=agency.stripe_customer_id, status="all", limit=10
                )

                if not stripe_subs.data:
                    self.stdout.write(self.style.WARNING("No subscriptions found in Stripe"))
                else:
                    self.stdout.write(f"Found {len(stripe_subs.data)} subscriptions in Stripe:")

                    # Create a set of existing Stripe subscription IDs in our database
                    local_sub_ids = set(
                        subscriptions.values_list("stripe_subscription_id", flat=True)
                    )

                    for idx, stripe_sub in enumerate(stripe_subs.data, 1):
                        self.stdout.write(f"\nStripe Subscription #{idx}:")
                        self.stdout.write(f"  ID: {stripe_sub.id}")
                        self.stdout.write(f"  Status: {stripe_sub.status}")
                        self.stdout.write(f"  Created: {stripe_sub.created}")

                        price_id = stripe_sub["items"]["data"][0]["price"]["id"]
                        self.stdout.write(f"  Price ID: {price_id}")

                        # Check if subscription exists in local database
                        if stripe_sub.id not in local_sub_ids:
                            self.stdout.write(self.style.WARNING("  Not found in local database"))

                            if fix_mode:
                                try:
                                    from django.db import transaction

                                    from subscriptions.models import Plan

                                    # Get the plan
                                    try:
                                        plan = Plan.objects.get(stripe_price_id=price_id)
                                    except Plan.DoesNotExist:
                                        self.stdout.write(
                                            self.style.ERROR(
                                                f"  Plan with price ID {price_id} not found"
                                            )
                                        )
                                        continue

                                    # Parse dates
                                    from datetime import datetime
                                    from datetime import timezone as dt_timezone

                                    current_period_start = datetime.fromtimestamp(
                                        stripe_sub.current_period_start, tz=dt_timezone.utc
                                    )
                                    current_period_end = datetime.fromtimestamp(
                                        stripe_sub.current_period_end, tz=dt_timezone.utc
                                    )

                                    # Create subscription
                                    with transaction.atomic():
                                        new_sub = Subscription(
                                            agency=agency,
                                            plan=plan,
                                            stripe_subscription_id=stripe_sub.id,
                                            is_active=stripe_sub.status == "active",
                                            status=stripe_sub.status,
                                            current_period_start=current_period_start,
                                            current_period_end=current_period_end,
                                            is_expired=stripe_sub.status in ["canceled", "unpaid"],
                                        )
                                        new_sub.save()
                                        self.stdout.write(
                                            self.style.SUCCESS(
                                                f"  Fixed: Created local subscription record"
                                            )
                                        )
                                except Exception as e:
                                    self.stdout.write(
                                        self.style.ERROR(
                                            f"  Error creating local subscription: {e}"
                                        )
                                    )

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error listing Stripe subscriptions: {e}"))

        # Final summary
        self.stdout.write("\nDebugging summary:")
        if fix_mode:
            self.stdout.write("Fixes were applied where possible.")
        else:
            self.stdout.write("Run with --fix to automatically repair issues.")
