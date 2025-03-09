# /workspace/shiftwise/subscriptions/management/commands/sync_all_subscriptions.py

import logging
import stripe
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime, timezone as dt_timezone

from accounts.models import Agency
from subscriptions.models import Subscription, Plan

logger = logging.getLogger(__name__)
stripe.api_key = settings.STRIPE_SECRET_KEY

class Command(BaseCommand):
    help = "Sync all subscription data with Stripe"

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force update all subscriptions, not just potentially outdated ones',
        )

    def handle(self, *args, **options):
        force = options.get('force', False)
        agencies = Agency.objects.filter(stripe_customer_id__isnull=False)
        
        self.stdout.write(f"Checking {agencies.count()} agencies with Stripe customer IDs")
        
        synced_count = 0
        error_count = 0
        
        for agency in agencies:
            try:
                # Get subscriptions from Stripe
                stripe_subs = stripe.Subscription.list(
                    customer=agency.stripe_customer_id,
                    status="active",
                    limit=5
                )
                
                if stripe_subs.data:
                    # Sort by created date (newest first)
                    stripe_subs_sorted = sorted(
                        stripe_subs.data, 
                        key=lambda x: x.get('created', 0),
                        reverse=True
                    )
                    
                    # Use the most recent active subscription
                    stripe_sub = stripe_subs_sorted[0]
                    
                    try:
                        # Get local subscription
                        try:
                            subscription = agency.subscription
                            needs_update = force
                            
                            if not needs_update:
                                # Check if data is outdated
                                if subscription.stripe_subscription_id != stripe_sub.id:
                                    needs_update = True
                                elif not subscription.is_active:
                                    needs_update = True
                                
                            if needs_update:
                                # Update the subscription
                                plan_id = stripe_sub["items"]["data"][0]["price"]["id"]
                                plan = Plan.objects.get(stripe_price_id=plan_id)
                                
                                subscription.plan = plan
                                subscription.stripe_subscription_id = stripe_sub.id
                                subscription.is_active = True
                                subscription.status = stripe_sub.status
                                subscription.current_period_start = datetime.fromtimestamp(
                                    stripe_sub.current_period_start, tz=dt_timezone.utc
                                )
                                subscription.current_period_end = datetime.fromtimestamp(
                                    stripe_sub.current_period_end, tz=dt_timezone.utc
                                )
                                subscription.is_expired = False
                                subscription.save()
                                
                                self.stdout.write(self.style.SUCCESS(
                                    f"Updated subscription for {agency.name} from Stripe data"
                                ))
                                synced_count += 1
                            
                        except Subscription.DoesNotExist:
                            # Create a new subscription
                            plan_id = stripe_sub["items"]["data"][0]["price"]["id"]
                            plan = Plan.objects.get(stripe_price_id=plan_id)
                            
                            subscription = Subscription.objects.create(
                                agency=agency,
                                plan=plan,
                                stripe_subscription_id=stripe_sub.id,
                                is_active=True,
                                status=stripe_sub.status,
                                current_period_start=datetime.fromtimestamp(
                                    stripe_sub.current_period_start, tz=dt_timezone.utc
                                ),
                                current_period_end=datetime.fromtimestamp(
                                    stripe_sub.current_period_end, tz=dt_timezone.utc
                                ),
                                is_expired=False
                            )
                            
                            self.stdout.write(self.style.SUCCESS(
                                f"Created new subscription for {agency.name} from Stripe data"
                            ))
                            synced_count += 1
                            
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(
                            f"Error processing subscription for {agency.name}: {e}"
                        ))
                        error_count += 1
                
                else:
                    # No active subscription in Stripe, deactivate local subscription
                    try:
                        subscription = agency.subscription
                        if subscription.is_active:
                            subscription.is_active = False
                            subscription.status = "canceled"
                            subscription.save()
                            self.stdout.write(self.style.WARNING(
                                f"Deactivated subscription for {agency.name} - not found in Stripe"
                            ))
                            synced_count += 1
                    except Subscription.DoesNotExist:
                        # No subscription record exists for this agency - nothing to sync
                        pass
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(
                    f"Error syncing subscriptions for {agency.name}: {e}"
                ))
                error_count += 1
        
        self.stdout.write(f"\nSummary:")
        self.stdout.write(f"Agencies processed: {agencies.count()}")
        self.stdout.write(f"Subscriptions synced: {synced_count}")
        self.stdout.write(f"Errors encountered: {error_count}")