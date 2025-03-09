# /workspace/shiftwise/subscriptions/views.py

import logging
from collections import defaultdict
from datetime import datetime, timezone as datetime_timezone

import stripe
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView
from django.db.models import Q

from accounts.models import Agency, Profile
from core.mixins import AgencyOwnerRequiredMixin
from subscriptions.models import Plan, Subscription

from .utils import create_stripe_customer

logger = logging.getLogger(__name__)
stripe.api_key = settings.STRIPE_SECRET_KEY


class SubscriptionHomeView(LoginRequiredMixin, TemplateView):
    template_name = "subscriptions/subscription_home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        if user.is_authenticated:
            try:
                profile = user.profile
            except Profile.DoesNotExist:
                messages.error(
                    self.request, "User profile does not exist. Please contact support."
                )
                logger.error(f"Profile does not exist for user: {user.username}")
                return context

            agency = profile.agency

            if agency is None:
                messages.error(
                    self.request,
                    "Your agency information is missing. Please contact support.",
                )
                logger.error(f"Agency is None for user: {user.username}")
                return context

            # Get current subscription
            try:
                # Determine if Stripe sync is needed
                should_sync = False
                subscription = None
                
                try:
                    subscription = agency.subscription
                    if subscription.is_active and subscription.current_period_end:
                        time_till_expiry = subscription.current_period_end - timezone.now()
                        if time_till_expiry.total_seconds() < 86400:  # Less than a day
                            should_sync = True
                except Subscription.DoesNotExist:
                    pass
                
                # Sync with Stripe if needed
                if should_sync and agency.stripe_customer_id:
                    try:
                        stripe_subscriptions = stripe.Subscription.list(
                            customer=agency.stripe_customer_id,
                            status="active",
                            limit=1
                        )
                        
                        if stripe_subscriptions.data:
                            stripe_sub = stripe_subscriptions.data[0]
                            
                            if subscription and subscription.stripe_subscription_id == stripe_sub.id:
                                current_period_end = datetime.fromtimestamp(
                                    stripe_sub.current_period_end, tz=datetime_timezone.utc
                                )
                                subscription.current_period_end = current_period_end
                                subscription.is_active = stripe_sub.status == "active"
                                subscription.status = stripe_sub.status
                                subscription.save()
                                logger.info(f"Synced subscription data from Stripe for {agency.name}")
                    except stripe.error.StripeError as e:
                        logger.warning(f"Failed to sync subscription with Stripe: {e}")
                
                # Check subscription status
                try:
                    if not subscription:
                        subscription = agency.subscription
                        
                    if (
                        subscription.is_active
                        and subscription.current_period_end
                        and subscription.current_period_end > timezone.now()
                    ):
                        context["subscription"] = subscription
                        context["current_plan"] = subscription.plan
                        context["has_active_subscription"] = True
                    else:
                        context["subscription"] = None
                        context["current_plan"] = None
                        context["has_active_subscription"] = False
                except Subscription.DoesNotExist:
                    context["subscription"] = None
                    context["current_plan"] = None
                    context["has_active_subscription"] = False
                    logger.warning(f"No active subscription for agency: {agency.name}")
            except Exception as e:
                messages.error(
                    self.request,
                    "An error occurred while retrieving your subscription.",
                )
                logger.exception(f"Error retrieving subscription: {e}")
                context["subscription"] = None
                context["current_plan"] = None
                context["has_active_subscription"] = False

            # Organize available plans by name and billing cycle
            plans = Plan.objects.filter(is_active=True).order_by(
                "name", "billing_cycle"
            )

            plan_dict = defaultdict(dict)
            for plan in plans:
                if plan.billing_cycle.lower() == "monthly":
                    plan_dict[plan.name]["monthly_plan"] = plan
                elif plan.billing_cycle.lower() == "yearly":
                    plan_dict[plan.name]["yearly_plan"] = plan

            available_plans = []
            for plan_name, plans in plan_dict.items():
                if not plans.get("monthly_plan") and not plans.get("yearly_plan"):
                    logger.warning(
                        f"No monthly or yearly plan found for {plan_name}. Skipping."
                    )
                    continue

                description = (
                    plans.get("monthly_plan").description
                    if plans.get("monthly_plan")
                    else plans.get("yearly_plan").description
                )

                is_current_monthly = False
                is_current_yearly = False
                
                if context.get("has_active_subscription") and context.get("current_plan"):
                    current_plan = context["current_plan"]
                    if plans.get("monthly_plan") and plans["monthly_plan"].id == current_plan.id:
                        is_current_monthly = True
                    if plans.get("yearly_plan") and plans["yearly_plan"].id == current_plan.id:
                        is_current_yearly = True
                
                available_plans.append(
                    {
                        "name": plan_name,
                        "description": description,
                        "monthly_plan": plans.get("monthly_plan"),
                        "yearly_plan": plans.get("yearly_plan"),
                        "is_current_monthly": is_current_monthly,
                        "is_current_yearly": is_current_yearly,
                    }
                )

            context["available_plans"] = available_plans

        return context


class SubscribeView(LoginRequiredMixin, View):
    def get(self, request, plan_id, *args, **kwargs):
        return self.process_subscription(request, plan_id)

    def post(self, request, plan_id, *args, **kwargs):
        return self.process_subscription(request, plan_id)

    def process_subscription(self, request, plan_id):
        user = request.user

        try:
            profile = user.profile
        except Profile.DoesNotExist:
            messages.error(request, "Please complete your profile before subscribing.")
            logger.error(f"Profile does not exist for user: {user.username}")
            return redirect("accounts:update_profile")

        agency = profile.agency
        if not agency:
            messages.error(request, "Please create an agency before subscribing.")
            logger.error(f"Agency is None for user: {user.username}")
            return redirect("accounts:create_agency")

        if not user.groups.filter(name="Agency Owners").exists():
            messages.error(request, "Only agency owners can subscribe.")
            logger.warning(
                f"User {user.username} attempted to subscribe without being an agency owner."
            )
            return redirect("subscriptions:subscription_home")

        plan = get_object_or_404(Plan, id=plan_id, is_active=True)

        # Ensure valid Stripe customer ID
        if not agency.stripe_customer_id:
            try:
                customer = create_stripe_customer(agency)
                agency.stripe_customer_id = customer.id
                agency.save(update_fields=["stripe_customer_id"])
                logger.info(f"Created new Stripe customer for agency: {agency.name}")
            except stripe.error.StripeError as e:
                messages.error(request, "Failed to create Stripe customer.")
                logger.exception(f"Stripe error while creating customer: {e}")
                return redirect("subscriptions:subscription_home")
            except Exception as e:
                messages.error(request, "An unexpected error occurred. Please try again.")
                logger.exception(f"Unexpected error while creating customer: {e}")
                return redirect("subscriptions:subscription_home")
        else:
            # Validate existing customer
            try:
                stripe.Customer.retrieve(agency.stripe_customer_id)
            except stripe.error.InvalidRequestError:
                try:
                    customer = create_stripe_customer(agency)
                    agency.stripe_customer_id = customer.id
                    agency.save(update_fields=["stripe_customer_id"])
                    logger.info(f"Created replacement Stripe customer for agency: {agency.name}")
                except stripe.error.StripeError as e:
                    messages.error(request, "Failed to create Stripe customer.")
                    logger.exception(f"Stripe error while creating replacement customer: {e}")
                    return redirect("subscriptions:subscription_home")
                except Exception as e:
                    messages.error(request, "An unexpected error occurred. Please try again.")
                    logger.exception(f"Unexpected error while creating replacement customer: {e}")
                    return redirect("subscriptions:subscription_home")
            except stripe.error.StripeError as e:
                messages.error(request, "Failed to retrieve Stripe customer.")
                logger.exception(f"Stripe error while retrieving customer: {e}")
                return redirect("subscriptions:subscription_home")
            except Exception as e:
                messages.error(request, "An unexpected error occurred. Please try again.")
                logger.exception(f"Unexpected error while retrieving customer: {e}")
                return redirect("subscriptions:subscription_home")

        # Redirect if subscription already active
        if hasattr(agency, "subscription") and agency.subscription.is_active:
            messages.info(
                request,
                "You already have an active subscription. Manage your subscription instead.",
            )
            logger.info(f"Agency {agency.name} already has an active subscription.")
            return redirect("subscriptions:manage_subscription")

        try:
            customer = stripe.Customer.retrieve(agency.stripe_customer_id)
            logger.info(
                f"Stripe customer retrieved for agency: {agency.name}, Customer ID: {customer.id}"
            )
        except stripe.error.StripeError as e:
            messages.error(request, "Failed to retrieve Stripe customer.")
            logger.exception(f"Stripe error while retrieving customer: {e}")
            return redirect("subscriptions:subscription_home")
        except Exception as e:
            messages.error(request, "An unexpected error occurred. Please try again.")
            logger.exception(f"Unexpected error while retrieving customer: {e}")
            return redirect("subscriptions:subscription_home")

        # Create checkout session
        try:
            checkout_session = stripe.checkout.Session.create(
                customer=customer.id,
                payment_method_types=["card"],
                line_items=[
                    {
                        "price": plan.stripe_price_id,
                        "quantity": 1,
                    },
                ],
                mode="subscription",
                success_url=request.build_absolute_uri(
                    reverse("subscriptions:subscription_success")
                ),
                cancel_url=request.build_absolute_uri(
                    reverse("subscriptions:subscription_cancel")
                ),
            )
            logger.info(
                f"Stripe Checkout Session created: {checkout_session.id} for agency: {agency.name}"
            )
            return redirect(checkout_session.url)
        except stripe.error.StripeError as e:
            messages.error(request, "There was an error creating the checkout session.")
            logger.exception(f"Stripe error while creating checkout session: {e}")
            return redirect("subscriptions:subscription_home")
        except Exception as e:
            messages.error(request, "An unexpected error occurred. Please try again.")
            logger.exception(f"Unexpected error while creating checkout session: {e}")
            return redirect("subscriptions:subscription_home")


def subscription_success(request):
    """Backup webhook handler for successful subscriptions"""
    user = request.user
    
    if user.is_authenticated:
        try:
            profile = user.profile
            agency = profile.agency
            
            if agency.stripe_customer_id:
                subscriptions = stripe.Subscription.list(
                    customer=agency.stripe_customer_id,
                    status="active",
                    limit=1
                )
                
                if subscriptions.data:
                    stripe_sub = subscriptions.data[0]
                    plan_id = stripe_sub["items"]["data"][0]["price"]["id"]
                    
                    try:
                        plan = Plan.objects.get(stripe_price_id=plan_id)
                        
                        current_period_start = datetime.fromtimestamp(
                            stripe_sub.current_period_start, tz=datetime_timezone.utc
                        )
                        current_period_end = datetime.fromtimestamp(
                            stripe_sub.current_period_end, tz=datetime_timezone.utc
                        )
                        
                        try:
                            subscription = agency.subscription
                            subscription.plan = plan
                            subscription.stripe_subscription_id = stripe_sub.id
                            subscription.is_active = True
                            subscription.status = stripe_sub.status
                            subscription.current_period_start = current_period_start
                            subscription.current_period_end = current_period_end
                            subscription.is_expired = False
                            subscription.save()
                            logger.info(f"Updated subscription in success page for {agency.name}")
                        except Subscription.DoesNotExist:
                            subscription = Subscription.objects.create(
                                agency=agency,
                                plan=plan,
                                stripe_subscription_id=stripe_sub.id,
                                is_active=True,
                                status=stripe_sub.status,
                                current_period_start=current_period_start,
                                current_period_end=current_period_end,
                                is_expired=False,
                            )
                            logger.info(f"Created new subscription in success page for {agency.name}")
                    except Plan.DoesNotExist:
                        logger.error(f"Plan with price ID {plan_id} does not exist.")
                
        except Exception as e:
            logger.exception(f"Error updating subscription in success page: {e}")
    
    messages.success(request, "Your subscription was successful!")
    return render(request, "subscriptions/success.html")


def subscription_cancel(request):
    messages.error(request, "Your subscription was cancelled.")
    return render(request, "subscriptions/cancel.html")


@method_decorator(csrf_exempt, name="dispatch")
class StripeWebhookView(View):
    def post(self, request, *args, **kwargs):
        payload = request.body
        sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")
        endpoint_secret = settings.STRIPE_WEBHOOK_SECRET

        if not sig_header:
            logger.error("Missing Stripe signature header.")
            return HttpResponse(status=400)

        try:
            event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
            logger.info(f"Stripe webhook received: {event['type']}")
        except ValueError as e:
            logger.exception(f"Invalid payload: {e}")
            return HttpResponse(status=400)
        except stripe.error.SignatureVerificationError as e:
            logger.exception(f"Invalid signature: {e}")
            return HttpResponse(status=400)

        event_type = event.get("type")
        event_data = event.get("data", {}).get("object", {})

        logger.info(f"Processing webhook event: {event_type}")
        logger.debug(f"Event data: {event_data}")

        try:
            if event_type == "checkout.session.completed":
                self.handle_checkout_session_completed(event_data)
            elif event_type == "invoice.payment_succeeded":
                self.handle_invoice_paid(event_data)
            elif event_type == "customer.subscription.deleted":
                self.handle_subscription_deleted(event_data)
            elif event_type == "customer.subscription.updated":
                self.handle_subscription_updated(event_data)
            elif event_type == "customer.subscription.created":
                self.handle_subscription_created(event_data)
            else:
                logger.info(f"Unhandled event type: {event_type}")
        except Exception as e:
            logger.exception(f"Error handling webhook {event_type}: {e}")
            
        return HttpResponse(status=200)

    def handle_invoice_paid(self, invoice):
        """Updates subscription records after confirmed payment"""
        stripe_subscription_id = invoice.get("subscription")
        if not stripe_subscription_id:
            logger.warning("Invoice does not contain a subscription ID.")
            return

        try:
            local_subscription = Subscription.objects.get(
                stripe_subscription_id=stripe_subscription_id
            )
            logger.info(f"Invoice paid for subscription {stripe_subscription_id}.")

            # Refresh subscription data from Stripe
            stripe_subscription = stripe.Subscription.retrieve(stripe_subscription_id)
            
            local_subscription.status = stripe_subscription.status
            if hasattr(local_subscription, "last_payment_date"):
                local_subscription.last_payment_date = timezone.now()
                
            if stripe_subscription.current_period_end:
                local_subscription.current_period_end = datetime.fromtimestamp(
                    stripe_subscription.current_period_end, tz=datetime_timezone.utc
                )
                
            local_subscription.save()
            logger.info(f"Updated subscription details after payment for {stripe_subscription_id}.")

        except Subscription.DoesNotExist:
            logger.error(
                f"No local subscription found for Stripe Subscription ID: {stripe_subscription_id}"
            )
        except Exception as e:
            logger.exception(f"Error handling invoice.payment_succeeded: {e}")

    def handle_subscription_deleted(self, subscription):
        """Deactivates subscription when deleted in Stripe"""
        stripe_subscription_id = subscription.get("id")
        logger.debug(
            f"Handling subscription deletion for Stripe Subscription ID: {stripe_subscription_id}"
        )
        try:
            local_subscription = Subscription.objects.get(
                stripe_subscription_id=stripe_subscription_id
            )
            local_subscription.is_active = False
            local_subscription.status = "canceled"
            local_subscription.save()
            logger.info(f"Subscription {stripe_subscription_id} deactivated.")
        except Subscription.DoesNotExist:
            logger.warning(
                f"Subscription with ID {stripe_subscription_id} does not exist in the local database."
            )
        except Exception as e:
            logger.exception(
                f"Unexpected error while handling subscription deletion: {e}"
            )

    def handle_subscription_updated(self, subscription):
        """Syncs subscription updates from Stripe"""
        stripe_subscription_id = subscription.get("id")
        try:
            local_subscription = Subscription.objects.get(
                stripe_subscription_id=stripe_subscription_id
            )
            
            local_subscription.is_active = subscription.get("status") == "active"
            local_subscription.status = subscription.get(
                "status", local_subscription.status
            )
            
            current_period_end = subscription.get("current_period_end")
            if current_period_end:
                local_subscription.current_period_end = datetime.fromtimestamp(
                    current_period_end, tz=datetime_timezone.utc
                )
                
            current_period_start = subscription.get("current_period_start")
            if current_period_start:
                local_subscription.current_period_start = datetime.fromtimestamp(
                    current_period_start, tz=datetime_timezone.utc
                )
            
            # Update plan if price has changed
            if subscription.get("items", {}).get("data"):
                new_plan_id = subscription["items"]["data"][0]["price"]["id"]
                
                try:
                    new_plan = Plan.objects.get(stripe_price_id=new_plan_id)
                    if local_subscription.plan.stripe_price_id != new_plan_id:
                        local_subscription.plan = new_plan
                        logger.info(
                            f"Subscription plan updated to {new_plan.name} for agency: {local_subscription.agency.name}"
                        )
                except Plan.DoesNotExist:
                    logger.warning(f"Plan with price ID {new_plan_id} does not exist in database.")
            
            local_subscription.save()
            logger.info(
                f"Subscription {stripe_subscription_id} updated for agency: {local_subscription.agency.name}"
            )
        except Subscription.DoesNotExist:
            logger.error(
                f"Subscription with ID {stripe_subscription_id} does not exist in local database."
            )
        except Plan.DoesNotExist:
            logger.exception(
                f"Plan with price ID from subscription {stripe_subscription_id} does not exist."
            )
        except ValidationError as ve:
            logger.exception(f"Validation error while updating subscription: {ve}")
        except Exception as e:
            logger.exception(
                f"Unexpected error while handling subscription update: {e}"
            )

    def handle_checkout_session_completed(self, session):
        """Processes newly completed checkout sessions"""
        customer_id = session.get("customer")
        subscription_id = session.get("subscription")

        logger.debug(
            f"Processing checkout.session.completed for customer {customer_id}"
        )

        try:
            stripe_subscription = stripe.Subscription.retrieve(subscription_id)
            logger.debug(f"Retrieved Stripe Subscription: {stripe_subscription}")

            plan_id = stripe_subscription["items"]["data"][0]["price"]["id"]
            logger.debug(f"Plan ID from Stripe: {plan_id}")

            current_period_start = datetime.fromtimestamp(
                stripe_subscription["current_period_start"], tz=datetime_timezone.utc
            )
            current_period_end = datetime.fromtimestamp(
                stripe_subscription["current_period_end"], tz=datetime_timezone.utc
            )

            agency = Agency.objects.get(stripe_customer_id=customer_id)
            logger.debug(f"Found Agency: {agency.name}")

            plan = Plan.objects.get(stripe_price_id=plan_id)
            logger.debug(f"Found Plan: {plan.name}")

            # Check for existing subscription
            existing_subscription = None
            try:
                existing_subscription = agency.subscription
                logger.debug(f"Existing Subscription found: {existing_subscription}")
            except Subscription.DoesNotExist:
                logger.debug("No existing Subscription found for agency.")
            
            # Handle case of new subscription with old one still active
            if existing_subscription and existing_subscription.stripe_subscription_id != subscription_id:
                try:
                    old_sub = stripe.Subscription.retrieve(existing_subscription.stripe_subscription_id)
                    if old_sub.status == 'active':
                        logger.warning(
                            f"Agency {agency.name} has a new subscription {subscription_id} but old subscription {existing_subscription.stripe_subscription_id} is still active."
                        )
                except stripe.error.StripeError:
                    logger.info(f"Old subscription {existing_subscription.stripe_subscription_id} no longer exists in Stripe.")
            
            # Create or update subscription record
            if existing_subscription:
                subscription = existing_subscription
                subscription.plan = plan
                subscription.stripe_subscription_id = subscription_id
                subscription.is_active = True
                subscription.status = stripe_subscription["status"]
                subscription.current_period_start = current_period_start
                subscription.current_period_end = current_period_end
                subscription.is_expired = False
            else:
                subscription = Subscription(
                    agency=agency,
                    plan=plan,
                    stripe_subscription_id=subscription_id,
                    is_active=True,
                    status=stripe_subscription["status"],
                    current_period_start=current_period_start,
                    current_period_end=current_period_end,
                    is_expired=False,
                )

            subscription.full_clean()
            subscription.save()
            logger.info(f"Subscription created/updated for agency {agency.name}")

        except Agency.DoesNotExist:
            logger.exception(f"Agency with customer ID {customer_id} does not exist.")
        except Plan.DoesNotExist:
            logger.exception(f"Plan with price ID {plan_id} does not exist.")
        except ValidationError as ve:
            logger.exception(f"Validation error while updating subscription: {ve}")
        except Exception as e:
            logger.exception(f"Unexpected error while handling checkout session: {e}")

    def handle_subscription_created(self, subscription):
        """Records newly created Stripe subscriptions"""
        stripe_subscription_id = subscription.get("id")
        customer_id = subscription.get("customer")
        
        try:
            if subscription.get("items", {}).get("data"):
                plan_id = subscription["items"]["data"][0]["price"]["id"]
                
                current_period_start = datetime.fromtimestamp(
                    subscription["current_period_start"], tz=datetime_timezone.utc
                )
                current_period_end = datetime.fromtimestamp(
                    subscription["current_period_end"], tz=datetime_timezone.utc
                )

                logger.info(f"Subscription created: {stripe_subscription_id}")

                agency = Agency.objects.get(stripe_customer_id=customer_id)
                logger.debug(f"Found Agency: {agency.name}")

                plan = Plan.objects.get(stripe_price_id=plan_id)
                logger.debug(f"Found Plan: {plan.name}")

                try:
                    existing_subscription = agency.subscription
                    
                    if existing_subscription.stripe_subscription_id == stripe_subscription_id:
                        existing_subscription.plan = plan
                        existing_subscription.is_active = True
                        existing_subscription.status = subscription.get("status", "active")
                        existing_subscription.current_period_start = current_period_start
                        existing_subscription.current_period_end = current_period_end
                        existing_subscription.is_expired = False
                        existing_subscription.save()
                        logger.info(f"Updated existing subscription {stripe_subscription_id} for agency {agency.name}")
                    else:
                        logger.warning(
                            f"Agency {agency.name} already has subscription {existing_subscription.stripe_subscription_id} but received creation event for {stripe_subscription_id}"
                        )
                except Subscription.DoesNotExist:
                    subscription_record = Subscription(
                        agency=agency,
                        plan=plan,
                        stripe_subscription_id=stripe_subscription_id,
                        is_active=True,
                        status=subscription.get("status", "active"),
                        current_period_start=current_period_start,
                        current_period_end=current_period_end,
                        is_expired=False,
                    )
                    subscription_record.save()
                    logger.info(f"Created new subscription {stripe_subscription_id} for agency {agency.name}")
            else:
                logger.warning(f"Subscription {stripe_subscription_id} has no items data")

        except Agency.DoesNotExist:
            logger.exception(f"Agency with customer ID {customer_id} does not exist.")
        except Plan.DoesNotExist:
            logger.exception(f"Plan with price ID {plan_id} does not exist.")
        except ValidationError as ve:
            logger.exception(
                f"Validation error while creating/updating subscription: {ve}"
            )
        except Exception as e:
            logger.exception(
                f"Unexpected error while handling subscription creation: {e}"
            )


stripe_webhook = StripeWebhookView.as_view()


class SubscriptionChangeView(
    LoginRequiredMixin, AgencyOwnerRequiredMixin, TemplateView
):
    template_name = "subscriptions/subscription_form_base.html"
    change_type = None  # 'upgrade' or 'downgrade'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        if not self.change_type:
            raise NotImplementedError("Change type must be defined in subclasses.")

        try:
            profile = user.profile
            agency = profile.agency
            subscription = agency.subscription

            # Verify subscription status locally and with Stripe
            if not subscription.is_active:
                messages.error(
                    self.request, "Your subscription is not active and cannot be modified."
                )
                logger.warning(
                    f"User {user.username} attempted to modify an inactive subscription."
                )
                context["available_plans"] = []
                return context

            stripe_subscription = stripe.Subscription.retrieve(
                subscription.stripe_subscription_id
            )

            if stripe_subscription["status"] != "active":
                messages.error(
                    self.request, "Your subscription is not active and cannot be modified."
                )
                logger.warning(
                    f"User {user.username} attempted to modify a Stripe subscription with status {stripe_subscription['status']}."
                )

                # Sync local status with Stripe
                subscription.is_active = False
                subscription.status = stripe_subscription["status"]
                subscription.save()

                context["available_plans"] = []
                return context

            current_billing_cycle = subscription.plan.billing_cycle
            
            # Set plan filtering logic based on change type
            if self.change_type == "upgrade":
                filtered_plans = Plan.objects.filter(
                    price__gt=subscription.plan.price, is_active=True
                ).order_by("billing_cycle", "price")
                form_title = "Upgrade Your Subscription"
                button_label = "Upgrade Subscription"
            elif self.change_type == "downgrade":
                # For downgrades: show only next tier down plans
                current_price = subscription.plan.price
                lower_priced_plans = Plan.objects.filter(
                    price__lt=current_price, is_active=True
                ).order_by("-price")
                
                # Group by billing cycle
                monthly_plans = lower_priced_plans.filter(billing_cycle="monthly")
                yearly_plans = lower_priced_plans.filter(billing_cycle="yearly")
                
                # Get the highest priced plan in each billing cycle (next tier down)
                filtered_plans = []
                if monthly_plans.exists():
                    filtered_plans.append(monthly_plans.first())
                if yearly_plans.exists():
                    filtered_plans.append(yearly_plans.first())
                    
                form_title = "Downgrade Your Subscription"
                button_label = "Downgrade Subscription"
            else:
                filtered_plans = []
                form_title = "Change Subscription"
                button_label = "Change Subscription"

            # Separate plans by billing cycle
            same_cycle_plans = []
            diff_cycle_plans = []
            
            for plan in filtered_plans:
                if plan.billing_cycle == current_billing_cycle:
                    same_cycle_plans.append(plan)
                elif plan.name == subscription.plan.name:
                    # Only include different cycle plans of the same tier
                    diff_cycle_plans.append(plan)

            # Include current plan for comparison
            if not any(plan.id == subscription.plan.id for plan in same_cycle_plans):
                same_cycle_plans.append(subscription.plan)
            
            # Sort plans by price
            same_cycle_plans = sorted(same_cycle_plans, 
                                    key=lambda p: p.price,
                                    reverse=(self.change_type == "downgrade"))

            context["same_cycle_plans"] = same_cycle_plans
            context["diff_cycle_plans"] = diff_cycle_plans
            context["form_title"] = form_title
            context["button_label"] = button_label
            context["current_subscription"] = subscription
            context["current_billing_cycle"] = current_billing_cycle
            context["change_type"] = self.change_type

        except Profile.DoesNotExist:
            messages.error(
                self.request, "User profile does not exist. Please contact support."
            )
            logger.error(f"Profile does not exist for user: {user.username}")
        except Subscription.DoesNotExist:
            messages.error(
                self.request, "Active subscription not found. Please subscribe first."
            )
            logger.error(
                f"No active subscription for agency: {agency.name if agency else 'N/A'}"
            )
        except stripe.error.StripeError as e:
            messages.error(
                self.request,
                "An error occurred while retrieving your subscription details. Please try again.",
            )
            logger.exception(f"Stripe error while retrieving subscription: {e}")
        except Exception as e:
            messages.error(
                self.request, "An unexpected error occurred. Please try again."
            )
            logger.exception(f"Unexpected error in SubscriptionChangeView: {e}")

        return context

    def post(self, request, *args, **kwargs):
        if not self.change_type:
            messages.error(request, "Invalid subscription change type.")
            logger.error("SubscriptionChangeView called without a valid change_type.")
            return redirect("subscriptions:subscription_home")

        plan_id = self.kwargs.get("plan_id")
        new_plan = get_object_or_404(Plan, id=plan_id, is_active=True)

        user = request.user

        try:
            profile = user.profile
            agency = profile.agency
            subscription = agency.subscription

            # Verify subscription is active in local database
            if not subscription.is_active:
                messages.error(
                    request, "Your subscription is not active and cannot be modified."
                )
                logger.warning(
                    f"User {user.username} attempted to modify an inactive subscription."
                )
                return redirect("subscriptions:manage_subscription")

            # Sync with Stripe's subscription status
            stripe_subscription = stripe.Subscription.retrieve(
                subscription.stripe_subscription_id
            )

            if stripe_subscription["status"] != "active":
                messages.error(
                    request, "Your subscription is not active and cannot be modified."
                )
                logger.warning(
                    f"User {user.username} attempted to modify a subscription with Stripe status {stripe_subscription['status']}."
                )

                subscription.is_active = False
                subscription.status = stripe_subscription["status"]
                subscription.save()

                return redirect("subscriptions:manage_subscription")
            
            # Track billing cycle changes for later processing
            is_cycle_change = subscription.plan.billing_cycle != new_plan.billing_cycle
            
            # Create new subscription checkout using Stripe's default proration behavior
            checkout_session = stripe.checkout.Session.create(
                customer=agency.stripe_customer_id,
                payment_method_types=["card"],
                line_items=[
                    {
                        "price": new_plan.stripe_price_id,
                        "quantity": 1,
                    },
                ],
                mode="subscription",
                success_url=request.build_absolute_uri(
                    reverse("subscriptions:subscription_change_success")
                ),
                cancel_url=request.build_absolute_uri(
                    reverse("subscriptions:subscription_cancel")
                )
            )
            
            # Store data for post-checkout processing
            request.session['checkout_session_id'] = checkout_session.id
            request.session['change_plan_id'] = plan_id
            request.session['old_subscription_id'] = subscription.stripe_subscription_id
            request.session['is_cycle_change'] = is_cycle_change
            
            return redirect(checkout_session.url)

        except Subscription.DoesNotExist:
            messages.error(
                request, "Active subscription not found. Please subscribe first."
            )
            logger.error(
                f"No active subscription for agency: {agency.name if agency else 'N/A'}"
            )
            return redirect("subscriptions:subscription_home")
        except stripe.error.StripeError as e:
            messages.error(
                request,
                f"An error occurred while changing your subscription: {str(e)}",
            )
            logger.exception(f"Stripe error during subscription change: {e}")
            return redirect("subscriptions:subscription_home")
        except Exception as e:
            messages.error(request, f"An unexpected error occurred: {str(e)}")
            logger.exception(f"Unexpected error during subscription change: {e}")
            return redirect("subscriptions:subscription_home")


def subscription_change_success(request):
    """Finalizes subscription changes after successful checkout"""
    session_id = request.session.pop('checkout_session_id', None)
    plan_id = request.session.pop('change_plan_id', None)
    old_subscription_id = request.session.pop('old_subscription_id', None)
    is_cycle_change = request.session.pop('is_cycle_change', False)
    
    if session_id and old_subscription_id:
        try:
            checkout_session = stripe.checkout.Session.retrieve(session_id)
            
            if checkout_session.status == 'complete':
                new_subscription_id = checkout_session.subscription
                
                user = request.user
                profile = user.profile
                agency = profile.agency
                
                if is_cycle_change:
                    try:
                        stripe.Subscription.delete(old_subscription_id)
                        logger.info(f"Cancelled old subscription: {old_subscription_id} after billing cycle change")
                    except stripe.error.StripeError as e:
                        logger.warning(f"Error cancelling old subscription: {e}")
                
                # Get latest subscription data from Stripe
                stripe_subscription = stripe.Subscription.retrieve(new_subscription_id)
                plan_id_from_stripe = stripe_subscription["items"]["data"][0]["price"]["id"]
                
                try:
                    new_plan = Plan.objects.get(stripe_price_id=plan_id_from_stripe)
                except Plan.DoesNotExist:
                    if plan_id:
                        new_plan = Plan.objects.get(id=plan_id)
                    else:
                        logger.error(f"Could not find plan for Stripe price ID: {plan_id_from_stripe}")
                        messages.warning(request, "Your subscription was changed but we couldn't identify the plan. Please contact support.")
                        return render(request, "subscriptions/success.html")
                
                current_period_start = datetime.fromtimestamp(
                    stripe_subscription["current_period_start"], tz=datetime_timezone.utc
                )
                current_period_end = datetime.fromtimestamp(
                    stripe_subscription["current_period_end"], tz=datetime_timezone.utc
                )
                
                try:
                    subscription = agency.subscription
                    subscription.plan = new_plan
                    subscription.stripe_subscription_id = new_subscription_id
                    subscription.is_active = True
                    subscription.status = stripe_subscription["status"]
                    subscription.current_period_start = current_period_start
                    subscription.current_period_end = current_period_end
                    subscription.is_expired = False
                    subscription.save()
                    logger.info(f"Updated subscription for {agency.name} to {new_plan.name}")
                    
                    if is_cycle_change:
                        messages.success(
                            request, 
                            f"Your subscription has been successfully changed to {new_plan.name} ({new_plan.get_billing_cycle_display()})."
                        )
                    else:
                        messages.success(
                            request, 
                            f"Your subscription has been successfully updated to {new_plan.name}."
                        )
                except Exception as e:
                    logger.exception(f"Error updating local subscription record: {e}")
                    messages.warning(
                        request, 
                        "Your subscription change was processed, but we encountered an error updating our records. Please contact support if you experience any issues."
                    )
            else:
                messages.warning(request, "Your subscription change was not completed. Please try again or contact support.")
                
        except Exception as e:
            logger.exception(f"Error processing subscription change: {e}")
            messages.warning(
                request, 
                "Your subscription change may have been successful, but we encountered an error updating our records. Please contact support if you experience any issues."
            )
    
    return render(request, "subscriptions/success.html")


class UpgradeSubscriptionView(SubscriptionChangeView):
    change_type = "upgrade"


class DowngradeSubscriptionView(SubscriptionChangeView):
    change_type = "downgrade"


class CancelSubscriptionView(LoginRequiredMixin, AgencyOwnerRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        user = request.user

        try:
            profile = user.profile
        except Profile.DoesNotExist:
            messages.error(
                request, "User profile does not exist. Please contact support."
            )
            logger.error(f"Profile does not exist for user: {user.username}")
            return redirect("subscriptions:subscription_home")

        agency = profile.agency

        if not agency:
            messages.error(
                request,
                "Your agency information is missing. Please contact support.",
            )
            logger.error(f"Agency is None for user: {user.username}")
            return redirect("subscriptions:subscription_home")

        if not agency.stripe_customer_id:
            messages.error(
                request, "No Stripe customer ID found. Please contact support."
            )
            logger.error(f"Stripe customer ID is missing for agency: {agency.name}")
            return redirect("subscriptions:subscription_home")

        try:
            subscriptions = stripe.Subscription.list(
                customer=agency.stripe_customer_id, status="active"
            )

            for subscription in subscriptions.auto_paging_iter():
                stripe.Subscription.delete(subscription.id)
                local_subscription = Subscription.objects.filter(
                    stripe_subscription_id=subscription.id
                ).first()
                if local_subscription:
                    local_subscription.is_active = False
                    local_subscription.status = "canceled"
                    local_subscription.save()
                    logger.info(
                        f"Subscription {subscription.id} deactivated for agency: {agency.name}"
                    )

            messages.success(request, "Your subscription has been cancelled.")
            return redirect("subscriptions:subscription_home")
        except stripe.error.StripeError as e:
            messages.error(request, "Unable to cancel your subscription.")
            logger.exception(f"Stripe error while cancelling subscription: {e}")
            return redirect("subscriptions:subscription_home")
        except Exception as e:
            messages.error(request, "An unexpected error occurred. Please try again.")
            logger.exception(f"Unexpected error while cancelling subscription: {e}")
            return redirect("subscriptions:subscription_home")


class ManageSubscriptionView(
    LoginRequiredMixin, AgencyOwnerRequiredMixin, TemplateView
):
    template_name = "subscriptions/manage_subscription.html"

    def get(self, request, *args, **kwargs):
        """Validates user access and Stripe customer info before rendering"""
        user = request.user

        try:
            profile = user.profile
        except Profile.DoesNotExist:
            messages.error(
                request, "User profile does not exist. Please contact support."
            )
            logger.error(f"Profile does not exist for user: {user.username}")
            return redirect("subscriptions:subscription_home")

        agency = profile.agency

        if not agency:
            messages.error(
                request,
                "Your agency information is missing. Please contact support.",
            )
            logger.error(f"Agency is None for user: {user.username}")
            return redirect("subscriptions:subscription_home")

        # Verify or create Stripe customer record
        try:
            if not agency.stripe_customer_id:
                customer = create_stripe_customer(agency)
                agency.stripe_customer_id = customer.id
                agency.save(update_fields=["stripe_customer_id"])
                logger.info(f"Created new Stripe customer for agency: {agency.name}")
            else:
                try:
                    stripe.Customer.retrieve(agency.stripe_customer_id)
                except stripe.error.InvalidRequestError:
                    customer = create_stripe_customer(agency)
                    agency.stripe_customer_id = customer.id
                    agency.save(update_fields=["stripe_customer_id"])
                    logger.info(f"Created replacement Stripe customer for agency: {agency.name}")
        except stripe.error.StripeError as e:
            messages.error(request, "Unable to verify Stripe customer. Please try again later.")
            logger.exception(f"Stripe error while verifying customer: {e}")
            return redirect("subscriptions:subscription_home")
        except Exception as e:
            messages.error(request, "An unexpected error occurred. Please try again.")
            logger.exception(f"Unexpected error during customer verification: {e}")
            return redirect("subscriptions:subscription_home")

        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        """Prepares subscription data from database and Stripe API"""
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        try:
            profile = user.profile
            agency = profile.agency

            # Get subscription from local database
            try:
                subscription = agency.subscription
                if (
                    subscription.is_active
                    and subscription.current_period_end
                    and subscription.current_period_end > timezone.now()
                ):
                    context["subscription"] = subscription
                    context["has_active_subscription"] = True
                    context["current_plan"] = subscription.plan
                    current_billing_cycle = subscription.plan.billing_cycle
                else:
                    context["subscription"] = None
                    context["has_active_subscription"] = False
                    context["current_plan"] = None
                    current_billing_cycle = None
            except Subscription.DoesNotExist:
                context["subscription"] = None
                context["has_active_subscription"] = False
                context["current_plan"] = None
                current_billing_cycle = None
                logger.warning(f"No active subscription for agency: {agency.name}")

            try:
                # Sync with Stripe subscription data
                if agency.stripe_customer_id:
                    # Get active Stripe subscriptions
                    subscriptions = stripe.Subscription.list(
                        customer=agency.stripe_customer_id, 
                        status="active",
                        expand=["data.default_payment_method"]
                    )
                    
                    # Include Stripe subscription details
                    if subscriptions.data:
                        context["stripe_subscriptions"] = subscriptions.data
                        context["has_stripe_subscription"] = True
                        
                        # Get payment information from recent invoice
                        try:
                            invoices = stripe.Invoice.list(
                                customer=agency.stripe_customer_id,
                                limit=1
                            )
                            if invoices.data:
                                context["latest_invoice"] = invoices.data[0]
                        except stripe.error.StripeError as e:
                            logger.warning(f"Could not retrieve invoice information: {e}")
                    else:
                        context["has_stripe_subscription"] = False
                    
                    # Create Stripe billing portal access
                    try:
                        portal_configuration = stripe.billing_portal.Configuration.list(
                            limit=1
                        ).data[0]
                        
                        billing_portal_session = stripe.billing_portal.Session.create(
                            customer=agency.stripe_customer_id,
                            configuration=portal_configuration.id,
                            return_url=self.request.build_absolute_uri(
                                reverse("subscriptions:manage_subscription")
                            ),
                        )
                        context["billing_portal_url"] = billing_portal_session.url
                    except Exception as e:
                        logger.warning(f"Error creating billing portal session: {e}")
                        # Attempt simpler portal creation if custom configuration fails
                        try:
                            billing_portal_session = stripe.billing_portal.Session.create(
                                customer=agency.stripe_customer_id,
                                return_url=self.request.build_absolute_uri(
                                    reverse("subscriptions:manage_subscription")
                                ),
                            )
                            context["billing_portal_url"] = billing_portal_session.url
                        except Exception as e:
                            logger.error(f"Error creating fallback billing portal session: {e}")
                
                # Determine plan upgrade/downgrade options
                if subscription and subscription.is_active:
                    current_plan = subscription.plan
                    
                    # Plans with same billing cycle and higher price
                    upgrade_plans = Plan.objects.filter(
                        billing_cycle=current_billing_cycle,
                        price__gt=current_plan.price, 
                        is_active=True
                    ).order_by("price")
                    
                    # Plans with same billing cycle and lower price
                    downgrade_plans = Plan.objects.filter(
                        billing_cycle=current_billing_cycle,
                        price__lt=current_plan.price, 
                        is_active=True
                    ).order_by("-price")
                    
                    # Same plan with different billing cycle
                    alternate_cycle = "yearly" if current_billing_cycle == "monthly" else "monthly"
                    alternate_cycle_plans = Plan.objects.filter(
                        name=current_plan.name,
                        billing_cycle=alternate_cycle,
                        is_active=True
                    ).order_by("price")
                    
                    context["upgrade_plans"] = upgrade_plans
                    context["downgrade_plans"] = downgrade_plans
                    context["alternate_cycle_plans"] = alternate_cycle_plans
                else:
                    context["upgrade_plans"] = Plan.objects.filter(is_active=True).order_by(
                        "price"
                    )
                    context["downgrade_plans"] = []
                    context["alternate_cycle_plans"] = []
            except stripe.error.StripeError as e:
                logger.exception(f"Stripe error while retrieving subscription details: {e}")
                context["error"] = "Unable to retrieve subscription details."
                context["has_active_subscription"] = False
            except Exception as e:
                logger.exception(f"Unexpected error while retrieving subscription details: {e}")
                context["error"] = "An unexpected error occurred. Please try again."
                context["has_active_subscription"] = False

        except Profile.DoesNotExist:
            logger.error(f"Profile does not exist for user: {user.username}")
            context["error"] = "User profile does not exist. Please contact support."
            context["has_active_subscription"] = False
        except Exception as e:
            logger.exception(f"Unexpected error in context preparation: {e}")
            context["error"] = "An unexpected error occurred. Please try again."
            context["has_active_subscription"] = False

        return context


class UpdatePaymentMethodView(LoginRequiredMixin, AgencyOwnerRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        """
        Redirects to Stripe Billing Portal for payment method management.
        """
        user = request.user

        try:
            profile = user.profile
        except Profile.DoesNotExist:
            messages.error(
                request, "User profile does not exist. Please contact support."
            )
            logger.error(f"Profile does not exist for user: {user.username}")
            return redirect("subscriptions:subscription_home")

        agency = profile.agency

        if not agency:
            messages.error(
                request, "Your agency information is missing. Please contact support."
            )
            logger.error(f"Agency is None for user: {user.username}")
            return redirect("subscriptions:subscription_home")

        # Ensure valid Stripe customer exists
        try:
            if not agency.stripe_customer_id:
                customer = create_stripe_customer(agency)
                agency.stripe_customer_id = customer.id
                agency.save(update_fields=["stripe_customer_id"])
                logger.info(f"Created new Stripe customer for agency: {agency.name}")
            else:
                try:
                    stripe.Customer.retrieve(agency.stripe_customer_id)
                except stripe.error.InvalidRequestError:
                    customer = create_stripe_customer(agency)
                    agency.stripe_customer_id = customer.id
                    agency.save(update_fields=["stripe_customer_id"])
                    logger.info(f"Created replacement Stripe customer for agency: {agency.name}")

            # Redirect to Stripe Billing Portal
            session = stripe.billing_portal.Session.create(
                customer=agency.stripe_customer_id,
                return_url=self.request.build_absolute_uri(
                    reverse("subscriptions:manage_subscription")
                ),
            )
            logger.info(f"Billing Portal session created for agency: {agency.name}")
            return redirect(session.url)
        except stripe.error.StripeError as e:
            messages.error(request, f"Unable to access Stripe Billing Portal: {str(e)}")
            logger.exception(f"Stripe error while handling payment method update: {e}")
            return redirect("subscriptions:subscription_home")
        except Exception as e:
            messages.error(request, "An unexpected error occurred. Please try again.")
            logger.exception(f"Unexpected error while updating payment method: {e}")
            return redirect("subscriptions:subscription_home")
