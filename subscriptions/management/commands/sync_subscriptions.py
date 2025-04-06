# /workspace/shiftwise/subscriptions/management/commands/sync_subscriptions.py

import logging
from datetime import datetime, timezone

import stripe

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import Agency
from subscriptions.models import Plan, Subscription

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Synchronize local subscriptions with Stripe"

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force update subscription data even for existing subscriptions",
        )
        parser.add_argument(
            "--agency_id",
            type=int,
            help="Sync subscriptions for a specific agency ID",
        )
        parser.add_argument(
            "--customer_id",
            help="Sync subscriptions for a specific Stripe customer ID",
        )
        parser.add_argument(
            "--cleanup",
            action="store_true",
            help="Deactivate local subscriptions not found in Stripe",
        )

    def handle(self, *args, **options):
        stripe.api_key = settings.STRIPE_SECRET_KEY
        force_update = options.get("force", False)
        agency_id = options.get("agency_id")
        customer_id = options.get("customer_id")
        cleanup = options.get("cleanup", False)

        # Metrics tracking
        sync_count = 0
        created_count = 0
        updated_count = 0
        deactivated_count = 0
        error_count = 0

        # Track IDs for cleanup operations
        processed_subscriptions = set()
        processed_agencies = set()

        # Configure Stripe query parameters
        subscription_args = {"limit": 100, "status": "active"}
        if customer_id:
            subscription_args["customer"] = customer_id
            self.stdout.write(f"Syncing subscriptions for Stripe customer: {customer_id}")

        # Validate agency filter if provided
        if agency_id:
            agencies = Agency.objects.filter(id=agency_id)
            if not agencies.exists():
                self.stdout.write(self.style.ERROR(f"Agency with ID {agency_id} not found"))
                return
            self.stdout.write(f"Syncing subscriptions for agency: {agencies.first().name}")
        else:
            agencies = None

        # Fetch active subscriptions from Stripe
        subscriptions = stripe.Subscription.list(**subscription_args)
        self.stdout.write(f"Found {len(subscriptions.data)} subscriptions in Stripe")

        for stripe_sub in subscriptions.auto_paging_iter():
            try:
                # Resolve the agency for this subscription
                if agency_id:
                    agency = agencies.first()
                    if agency.stripe_customer_id != stripe_sub.customer:
                        continue
                else:
                    try:
                        agency = Agency.objects.get(stripe_customer_id=stripe_sub.customer)
                    except Agency.DoesNotExist:
                        self.stdout.write(
                            self.style.WARNING(
                                f"No agency found for customer ID {stripe_sub.customer}"
                            )
                        )
                        continue

                processed_agencies.add(agency.id)

                stripe_sub_id = stripe_sub.id
                plan_id = stripe_sub["items"]["data"][0]["price"]["id"]

                try:
                    plan = Plan.objects.get(stripe_price_id=plan_id)
                except Plan.DoesNotExist:
                    self.stdout.write(
                        self.style.ERROR(
                            f"Plan with price ID {plan_id} does not exist. Skipping subscription {stripe_sub_id}."
                        )
                    )
                    error_count += 1
                    continue

                # Convert UNIX timestamps to datetime
                current_period_start = datetime.fromtimestamp(
                    stripe_sub.current_period_start, tz=timezone.utc
                )
                current_period_end = datetime.fromtimestamp(
                    stripe_sub.current_period_end, tz=timezone.utc
                )

                is_active = stripe_sub.status == "active"
                is_expired = stripe_sub.status in ["canceled", "unpaid"]

                # Create or update subscription record
                try:
                    with transaction.atomic():
                        subscription, created = Subscription.objects.get_or_create(
                            stripe_subscription_id=stripe_sub_id,
                            defaults={
                                "agency": agency,
                                "plan": plan,
                                "is_active": is_active,
                                "status": stripe_sub.status,
                                "current_period_start": current_period_start,
                                "current_period_end": current_period_end,
                                "is_expired": is_expired,
                            },
                        )

                        if created:
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f"Created subscription {stripe_sub_id} for agency {agency.name}"
                                )
                            )
                            created_count += 1
                        elif force_update:
                            subscription.agency = agency
                            subscription.plan = plan
                            subscription.is_active = is_active
                            subscription.status = stripe_sub.status
                            subscription.current_period_start = current_period_start
                            subscription.current_period_end = current_period_end
                            subscription.is_expired = is_expired
                            subscription.save()
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f"Updated subscription {stripe_sub_id} for agency {agency.name}"
                                )
                            )
                            updated_count += 1
                        else:
                            self.stdout.write(
                                f"Subscription {stripe_sub_id} already exists for agency {agency.name}"
                            )

                        sync_count += 1
                        processed_subscriptions.add(stripe_sub_id)

                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f"Error processing subscription {stripe_sub_id}: {e}")
                    )
                    error_count += 1

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"Error processing Stripe subscription {stripe_sub.id}: {e}")
                )
                error_count += 1

        # Handle subscription pruning
        if cleanup:
            self.stdout.write("Checking for local subscriptions not found in Stripe...")

            # Scope the query based on processed agencies
            query = Subscription.objects.filter(is_active=True)
            if agency_id:
                query = query.filter(agency_id=agency_id)
            elif processed_agencies:
                query = query.filter(agency_id__in=processed_agencies)

            # Deactivate subscriptions that no longer exist in Stripe
            for local_sub in query:
                if local_sub.stripe_subscription_id not in processed_subscriptions:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Local subscription {local_sub.id} with Stripe ID {local_sub.stripe_subscription_id} "
                            f"for agency {local_sub.agency.name} not found in Stripe"
                        )
                    )

                    if cleanup:
                        local_sub.is_active = False
                        local_sub.status = "canceled"
                        local_sub.is_expired = True
                        local_sub.save()
                        self.stdout.write(
                            self.style.SUCCESS(f"Deactivated local subscription {local_sub.id}")
                        )
                        deactivated_count += 1

        # Results summary
        self.stdout.write("\nSynchronization Summary:")
        self.stdout.write(f"Total subscriptions processed: {sync_count}")
        self.stdout.write(f"New subscriptions created: {created_count}")
        self.stdout.write(f"Existing subscriptions updated: {updated_count}")
        self.stdout.write(f"Local subscriptions deactivated: {deactivated_count}")
        self.stdout.write(f"Errors encountered: {error_count}")
