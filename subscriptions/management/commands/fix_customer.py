# /workspace/shiftwise/subscriptions/management/commands/fix_customer.py

import logging

import stripe

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import Agency, User

logger = logging.getLogger(__name__)
stripe.api_key = settings.STRIPE_SECRET_KEY


class Command(BaseCommand):
    help = "Fix specific customer problems"

    def add_arguments(self, parser):
        parser.add_argument(
            "agency_id",
            type=int,
            help="Agency ID to fix",
        )
        parser.add_argument(
            "--name",
            type=str,
            help="Name override",
        )
        parser.add_argument(
            "--email",
            type=str,
            help="Email override",
        )

    def handle(self, *args, **options):
        agency_id = options.get("agency_id")
        name_override = options.get("name")
        email_override = options.get("email")
        
        try:
            agency = Agency.objects.get(id=agency_id)
            self.stdout.write(f"Found agency: {agency.name} (ID: {agency.id})")
            
            if agency.owner:
                self.stdout.write(f"Owner: {agency.owner.username} (ID: {agency.owner.id})")
            else:
                self.stdout.write(self.style.WARNING("No owner assigned"))
            
            # Display current values
            self.stdout.write(f"Current name: {agency.name}")
            self.stdout.write(f"Current email: {agency.email}")
            self.stdout.write(f"Current customer ID: {agency.stripe_customer_id}")
            
            # Check if values need to be fixed
            name = name_override or agency.name
            email = email_override or agency.email
            
            if not email or "@" not in email:
                self.stdout.write(self.style.ERROR(f"Invalid email address: {email}"))
                if agency.owner and agency.owner.email:
                    email = agency.owner.email
                    self.stdout.write(self.style.WARNING(f"Using owner's email instead: {email}"))
                else:
                    self.stdout.write(self.style.ERROR("No valid email available. Aborting."))
                    return
            
            # Create new Stripe customer
            self.stdout.write(f"Creating new Stripe customer with name: {name}, email: {email}")
            
            with transaction.atomic():
                try:
                    # Create customer directly via API
                    customer = stripe.Customer.create(
                        name=name,
                        email=email,
                        metadata={
                            "agency_id": agency.id,
                        },
                    )
                    
                    # Save the new customer ID
                    old_id = agency.stripe_customer_id
                    agency.stripe_customer_id = customer.id
                    agency.save(update_fields=["stripe_customer_id"])
                    
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Created new Stripe customer: {customer.id}"
                        )
                    )
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Updated agency {agency.name}: old ID={old_id}, new ID={customer.id}"
                        )
                    )
                except stripe.error.StripeError as e:
                    self.stdout.write(self.style.ERROR(f"Stripe error: {e}"))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"Unexpected error: {e}"))
        
        except Agency.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"Agency with ID {agency_id} not found"))