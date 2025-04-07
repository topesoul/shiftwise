# /workspace/shiftwise/subscriptions/management/commands/verify_customer_ids.py

import logging

import stripe

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import Agency, User
from subscriptions.utils import create_stripe_customer

logger = logging.getLogger(__name__)
stripe.api_key = settings.STRIPE_SECRET_KEY


class Command(BaseCommand):
    help = "Verify and fix customer IDs for agencies"

    def add_arguments(self, parser):
        parser.add_argument(
            "--fix",
            action="store_true",
            help="Fix issues with customer IDs",
        )
        parser.add_argument(
            "--username",
            type=str,
            help="Check specific user by username",
        )
        parser.add_argument(
            "--agency-name",
            type=str,
            help="Check specific agency by name",
        )

    def handle(self, *args, **options):
        fix_issues = options.get("fix", False)
        username = options.get("username")
        agency_name = options.get("agency_name")
        
        # Track metrics
        total_agencies = 0
        valid_customers = 0
        invalid_customers = 0
        fixed_customers = 0
        
        # Filter agencies if specified
        agencies_query = Agency.objects.all()
        if username:
            try:
                user = User.objects.get(username=username)
                self.stdout.write(f"Found user {user.username} (ID: {user.id})")
                try:
                    agencies_query = agencies_query.filter(owner=user)
                    self.stdout.write(f"Looking at agencies owned by {user.username}")
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"Error filtering by owner: {e}"))
            except User.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"User with username '{username}' not found"))
                return
        
        if agency_name:
            agencies_query = agencies_query.filter(name__icontains=agency_name)
            self.stdout.write(f"Looking at agencies with name containing '{agency_name}'")
        
        agencies = agencies_query.order_by('name')
        total_agencies = agencies.count()
        
        self.stdout.write(f"Checking {total_agencies} agencies")
        
        # Process each agency
        for agency in agencies:
            self.stdout.write(f"\nChecking agency: {agency.name} (ID: {agency.id})")
            if agency.owner:
                self.stdout.write(f"Owner: {agency.owner.username} (ID: {agency.owner.id})")
            else:
                self.stdout.write(self.style.WARNING("No owner assigned"))
            
            # Check if customer ID exists
            customer_id = agency.stripe_customer_id
            self.stdout.write(f"Stripe Customer ID: {customer_id or 'None'}")
            
            if not customer_id:
                self.stdout.write(self.style.WARNING("No Stripe customer ID"))
                invalid_customers += 1
                
                if fix_issues:
                    try:
                        with transaction.atomic():
                            customer = create_stripe_customer(agency)
                            agency.stripe_customer_id = customer.id
                            agency.save(update_fields=["stripe_customer_id"])
                            self.stdout.write(
                                self.style.SUCCESS(f"Created new Stripe customer: {customer.id}")
                            )
                            valid_customers += 1
                            fixed_customers += 1
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"Error creating customer: {e}"))
                continue
            
            # Verify customer ID is valid
            try:
                customer = stripe.Customer.retrieve(customer_id)
                self.stdout.write(self.style.SUCCESS(f"Valid Stripe customer: {customer.email}"))
                valid_customers += 1
                
                # Check for subscriptions
                try:
                    subscriptions = stripe.Subscription.list(
                        customer=customer_id, limit=10
                    )
                    if subscriptions.data:
                        self.stdout.write(f"Found {len(subscriptions.data)} subscriptions:")
                        for sub in subscriptions.data:
                            self.stdout.write(f"  - ID: {sub.id}, Status: {sub.status}")
                    else:
                        self.stdout.write("No subscriptions found")
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"Error checking subscriptions: {e}"))
                
            except stripe.error.InvalidRequestError:
                self.stdout.write(self.style.ERROR("Invalid Stripe customer ID"))
                invalid_customers += 1
                
                if fix_issues:
                    try:
                        with transaction.atomic():
                            customer = create_stripe_customer(agency)
                            agency.stripe_customer_id = customer.id
                            agency.save(update_fields=["stripe_customer_id"])
                            self.stdout.write(
                                self.style.SUCCESS(f"Created replacement customer: {customer.id}")
                            )
                            valid_customers += 1
                            fixed_customers += 1
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"Error creating replacement: {e}"))
            
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error checking customer: {e}"))
                invalid_customers += 1
        
        # Final summary
        self.stdout.write("\n" + "="*40)
        self.stdout.write("SUMMARY")
        self.stdout.write("="*40)
        self.stdout.write(f"Total agencies checked: {total_agencies}")
        self.stdout.write(f"Valid customer IDs: {valid_customers}")
        self.stdout.write(f"Invalid customer IDs: {invalid_customers}")
        
        if fix_issues:
            self.stdout.write(f"Customer IDs fixed: {fixed_customers}")
        else:
            self.stdout.write("\nRun with --fix to repair invalid customer IDs")