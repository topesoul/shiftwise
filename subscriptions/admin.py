# /workspace/shiftwise/subscriptions/admin.py

from django.contrib import admin

from .models import Plan, Subscription


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    # Fields shown in the list view
    list_display = (
        "name",
        "billing_cycle",
        "price",
        "view_limit",
        "is_active",
        "is_recommended",
    )
    # Filter options in the sidebar
    list_filter = ("name", "billing_cycle", "is_active", "is_recommended")
    # Search functionality fields
    search_fields = ("name", "stripe_product_id", "stripe_price_id", "description")
    # Default ordering
    ordering = ("name", "billing_cycle")
    # Form organization
    fieldsets = (
        (
            "Basic Information",
            {"fields": ("name", "billing_cycle", "description", "price", "view_limit")},
        ),
        ("Stripe Integration", {"fields": ("stripe_product_id", "stripe_price_id")}),
        (
            "Plan Features",
            {
                "fields": (
                    "notifications_enabled",
                    "advanced_reporting",
                    "priority_support",
                    "shift_management",
                    "staff_performance",
                    "custom_integrations",
                )
            },
        ),
        ("Status", {"fields": ("is_active", "is_recommended")}),
    )


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    # Fields shown in the list view
    list_display = (
        "agency",
        "plan",
        "is_active",
        "is_expired",
        "current_period_start",
        "current_period_end",
        "stripe_subscription_id",
        "agency_stripe_customer_id",
    )
    # Filter options in the sidebar
    list_filter = ("is_active", "is_expired", "plan__name")
    # Search functionality fields
    search_fields = (
        "agency__name",
        "plan__name",
        "stripe_subscription_id",
        "agency__stripe_customer_id",
    )
    # Default ordering - newest subscriptions first
    ordering = ("-current_period_start",)
    # Fields that cannot be edited
    readonly_fields = ("created_at", "updated_at")

    fieldsets = (
        ("Subscription Details", {"fields": ("agency", "plan", "stripe_subscription_id")}),
        ("Status", {"fields": ("is_active", "is_expired")}),
        ("Billing Period", {"fields": ("current_period_start", "current_period_end")}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )

    def agency_stripe_customer_id(self, obj):
        """
        Shows the agency's Stripe customer ID in the admin list view
        """
        return obj.agency.stripe_customer_id if obj.agency else None

    agency_stripe_customer_id.short_description = "Agency Customer ID"
