# /workspace/shiftwise/core/mixins.py

import logging

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import UserPassesTestMixin
from django.contrib.messages import get_messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone

from subscriptions.models import Subscription

logger = logging.getLogger(__name__)
User = get_user_model()


class SuperuserRequiredMixin(UserPassesTestMixin):
    """Mixin to ensure that the user is a superuser."""

    def test_func(self):
        return self.request.user.is_superuser

    def handle_no_permission(self):
        messages.error(self.request, "You do not have permission to access this page.")
        return redirect("accounts:login_view")


class AgencyOwnerRequiredMixin(UserPassesTestMixin):
    """
    Mixin to ensure that the user is an agency owner or superuser.
    """

    def test_func(self):
        user = self.request.user
        return user.is_superuser or user.groups.filter(name="Agency Owners").exists()

    def handle_no_permission(self):
        messages.error(self.request, "You do not have permission to access this page.")
        logger.warning(
            f"User {self.request.user.username} attempted to access an owner-only page without permissions."
        )
        return redirect("home:home")


class AgencyManagerRequiredMixin(UserPassesTestMixin):
    """
    Mixin to ensure that the user is an agency manager or superuser.
    """

    def test_func(self):
        user = self.request.user
        return user.is_superuser or user.groups.filter(name="Agency Managers").exists()

    def handle_no_permission(self):
        messages.error(self.request, "You do not have permission to access this page.")
        logger.warning(
            f"User {self.request.user.username} attempted to access a manager-only page without permissions."
        )
        return redirect("home:home")


class AgencyStaffRequiredMixin(UserPassesTestMixin):
    """
    Mixin to ensure that the user is agency staff or a superuser.
    """

    def test_func(self):
        user = self.request.user
        return user.is_superuser or user.groups.filter(name="Agency Staff").exists()

    def handle_no_permission(self):
        messages.error(
            self.request, "You must be an Agency Staff member to access this page."
        )
        logger.warning(
            f"User {self.request.user.username} attempted to access a staff-only page without permissions."
        )
        return redirect("home:home")


class SubscriptionRequiredMixin(UserPassesTestMixin):
    """
    Mixin to ensure that the user's agency has an active subscription.
    """

    required_features = []  # List of features required to access the view

    def test_func(self):
        user = self.request.user
        if user.is_superuser:
            return True
        if not user.is_authenticated:
            return False
        try:
            agency = user.profile.agency
            if not agency:
                return False
            subscription = agency.subscription
            if not (subscription and subscription.is_active):
                return False
            plan = subscription.plan
            if plan and self.required_features:
                for feature in self.required_features:
                    if not getattr(plan, feature, False):
                        return False
            return True
        except Exception as e:
            logger.exception(f"Error in SubscriptionRequiredMixin for user {user.username}: {e}")
            return False

    def handle_no_permission(self):
        user = self.request.user
        # Clear existing messages
        storage = get_messages(self.request)
        list(storage)  # Force evaluation to clear messages
        if not user.is_authenticated:
            messages.error(self.request, "You must be logged in to access this page.")
            return redirect("accounts:login_view")
        else:
            messages.error(
                self.request,
                "Your agency does not have the necessary subscription to access this page.",
            )
            return redirect("subscriptions:subscription_home")


class FeatureRequiredMixin(UserPassesTestMixin):
    """
    Mixin to ensure that the user's subscription includes specific features.
    """

    required_features = []  # List of features required to access the view

    def test_func(self):
        if not self.required_features:
            return True  # No feature required
        user = self.request.user
        if user.is_superuser:
            return True
        if not user.is_authenticated:
            return False
        try:
            subscription_features = getattr(user.profile, "subscription_features", [])
            return all(feature in subscription_features for feature in self.required_features)
        except AttributeError:
            logger.exception(
                f"User {user.username} does not have 'subscription_features' attribute."
            )
            return False

    def handle_no_permission(self):
        user = self.request.user
        if not user.is_authenticated:
            messages.error(self.request, "You must be logged in to access this page.")
            return redirect("accounts:login_view")
        else:
            messages.error(
                self.request,
                "You do not have the necessary subscription features to access this page.",
            )
            return redirect("subscriptions:subscription_home")
