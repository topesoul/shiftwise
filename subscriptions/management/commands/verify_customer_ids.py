# /workspace/shiftwise/subscriptions/management/commands/verify_customer_ids.py

import logging

import stripe

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import Agency
from subscriptions.utils import create_stripe_customer

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Verify and fix Stripe customer IDs"

    def add_arguments(self, parser):
        parser.add_argument(
            "--fix",
            action="store_true",
            help="Fix invalid customer IDs",
        )
        parser.add_argument(
            "--agency_id",
            type=int,
            help="Verify a specific agency",
        )

    def handle(self, *args, **options):
        stripe.api_key = settings.STRIPE_SECRET_KEY
        fix_mode = options["fix"]
        agency_id = options.get("agency_id")

        if agency_id:
            agencies = Agency.objects.filter(id=agency_id)
            self.stdout.write(f"Verifying Stripe customer for agency ID: {agency_id}")
        else:
            agencies = Agency.objects.all()
            self.stdout.write(f"Verifying Stripe customers for {agencies.count()} agencies")

        valid_count = 0
        invalid_count = 0
        missing_count = 0
        fixed_count = 0

        for agency in agencies:
            if not agency.stripe_customer_id:
                self.stdout.write(
                    self.style.WARNING(
                        f"Agency {agency.id} ({agency.name}) is missing a Stripe customer ID"
                    )
                )
                missing_count += 1

                if fix_mode:
                    with transaction.atomic():
                        try:
                            customer = create_stripe_customer(agency)
                            agency.stripe_customer_id = customer.id
                            agency.save(update_fields=["stripe_customer_id"])
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f"Created new Stripe customer for agency: {agency.name} (ID: {customer.id})"
                                )
                            )
                            fixed_count += 1
                        except Exception as e:
                            self.stdout.write(
                                self.style.ERROR(
                                    f"Failed to create Stripe customer for agency {agency.name}: {e}"
                                )
                            )
            else:
                try:
                    # Try to retrieve the customer
                    customer = stripe.Customer.retrieve(agency.stripe_customer_id)
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Valid Stripe customer for agency {agency.id} ({agency.name}): {agency.stripe_customer_id}"
                        )
                    )
                    valid_count += 1
                except stripe.error.InvalidRequestError:
                    self.stdout.write(
                        self.style.ERROR(
                            f"Invalid Stripe customer ID for agency {agency.id} ({agency.name}): {agency.stripe_customer_id}"
                        )
                    )
                    invalid_count += 1

                    if fix_mode:
                        with transaction.atomic():
                            try:
                                # Create a new customer
                                customer = create_stripe_customer(agency)
                                old_id = agency.stripe_customer_id
                                agency.stripe_customer_id = customer.id
                                agency.save(update_fields=["stripe_customer_id"])
                                self.stdout.write(
                                    self.style.SUCCESS(
                                        f"Created replacement Stripe customer for agency: {agency.name} "
                                        f"(old: {old_id}, new: {customer.id})"
                                    )
                                )
                                fixed_count += 1
                            except Exception as e:
                                self.stdout.write(
                                    self.style.ERROR(
                                        f"Failed to create replacement Stripe customer for agency {agency.name}: {e}"
                                    )
                                )
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(
                            f"Error verifying Stripe customer for agency {agency.id} ({agency.name}): {e}"
                        )
                    )

        self.stdout.write("\nSummary:")
        self.stdout.write(f"Total agencies: {agencies.count()}")
        self.stdout.write(f"Valid Stripe customers: {valid_count}")
        self.stdout.write(f"Invalid Stripe customers: {invalid_count}")
        self.stdout.write(f"Missing Stripe customers: {missing_count}")

        if fix_mode:
            self.stdout.write(f"Fixed customers: {fixed_count}")
        else:
            self.stdout.write(
                self.style.WARNING("Run with --fix to repair invalid or missing customer IDs")
            )
