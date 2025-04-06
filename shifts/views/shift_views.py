# /workspace/shiftwise/shifts/views/shift_views.py

import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import (
    BooleanField,
    Case,
    Count,
    Exists,
    F,
    OuterRef,
    Q,
    When,
)
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)

from core.mixins import (
    AgencyManagerRequiredMixin,
    AgencyStaffRequiredMixin,
    FeatureRequiredMixin,
    SubscriptionRequiredMixin,
)
from shifts.forms import (
    AssignWorkerForm,
    ShiftCompletionForm,
    ShiftFilterForm,
    ShiftForm,
)
from shifts.models import Shift, ShiftAssignment
from shiftwise.utils import generate_shift_code, haversine_distance

logger = logging.getLogger(__name__)

User = get_user_model()


class ShiftListView(
    LoginRequiredMixin,
    AgencyStaffRequiredMixin,
    SubscriptionRequiredMixin,
    FeatureRequiredMixin,
    ListView,
):
    """List view for shifts with filtering capabilities"""

    required_features = ["shift_management"]
    model = Shift
    template_name = "shifts/shift_list.html"
    context_object_name = "shifts"
    paginate_by = 10
    ordering = ["shift_date", "start_time"]

    def get_queryset(self):
        user = self.request.user
        queryset = Shift.objects.all()

        if not user.is_superuser:
            agency = user.profile.agency
            queryset = queryset.filter(agency=agency)

        # Annotate with assignment counts and fullness status
        queryset = queryset.annotate(
            assignments_count=Count("assignments"),
            is_full_shift=Case(
                When(assignments_count__gte=F("capacity"), then=True),
                default=False,
                output_field=BooleanField(),
            ),
        )

        # Process filter form
        self.filter_form = ShiftFilterForm(self.request.GET or None)
        if self.filter_form.is_valid():
            date_from = self.filter_form.cleaned_data.get("date_from")
            date_to = self.filter_form.cleaned_data.get("date_to")
            status = self.filter_form.cleaned_data.get("status")
            search = self.filter_form.cleaned_data.get("search")
            shift_code = self.filter_form.cleaned_data.get("shift_code")
            address = self.filter_form.cleaned_data.get("address")

            if date_from:
                queryset = queryset.filter(shift_date__gte=date_from)
            if date_to:
                queryset = queryset.filter(shift_date__lte=date_to)
            if status and status != "all":
                if status == "available":
                    queryset = queryset.filter(is_full_shift=False)
                elif status == "booked":
                    queryset = queryset.filter(assignments_count__gt=0)
                elif status == "completed":
                    queryset = queryset.filter(status=Shift.STATUS_COMPLETED)
                elif status == "cancelled":
                    queryset = queryset.filter(status=Shift.STATUS_CANCELED)
            if search:
                queryset = queryset.filter(
                    Q(name__icontains=search)
                    | Q(shift_type__icontains=search)
                    | Q(agency__name__icontains=search)
                )
            if shift_code:
                queryset = queryset.filter(shift_code__icontains=shift_code)
            if address:
                queryset = queryset.filter(
                    Q(address_line1__icontains=address)
                    | Q(address_line2__icontains=address)
                    | Q(city__icontains=address)
                    | Q(county__icontains=address)
                    | Q(postcode__icontains=address)
                    | Q(country__icontains=address)
                )

        # Add assignment status for current user
        assignments = ShiftAssignment.objects.filter(
            shift=OuterRef("pk"), worker=user
        )
        queryset = queryset.annotate(is_assigned=Exists(assignments))

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["filter_form"] = self.filter_form

        user = self.request.user
        if (
            user.is_authenticated
            and hasattr(user, "profile")
            and user.profile.latitude
            and user.profile.longitude
        ):
            context["user_lat"] = user.profile.latitude
            context["user_lon"] = user.profile.longitude
        else:
            context["user_lat"] = None
            context["user_lon"] = None

        return context


class ShiftDetailView(
    LoginRequiredMixin,
    SubscriptionRequiredMixin,
    FeatureRequiredMixin,
    DetailView,
):
    """Detail view for shifts with role-based access control"""

    required_features = ["shift_management"]
    model = Shift
    template_name = "shifts/shift_detail.html"
    context_object_name = "shift"

    def get_queryset(self):
        user = self.request.user
        logger.debug(
            f"Current user: {user.username}, is_superuser: {user.is_superuser}"
        )

        queryset = Shift.objects.select_related("agency").prefetch_related(
            "assignments__worker"
        )

        if user.is_superuser:
            queryset = queryset.filter(is_active=True)
            logger.debug("User is superuser. Filtering active shifts.")
        elif user.groups.filter(name="Agency Owners").exists():
            agency = user.profile.agency
            if agency:
                queryset = queryset.filter(agency=agency, is_active=True)
                logger.debug(
                    f"User is an Agency Owner. Filtering shifts for agency: {agency}"
                )
            else:
                queryset = Shift.objects.none()
                logger.warning(
                    f"Agency Owner {user.username} does not have an associated agency."
                )
        elif user.groups.filter(name="Agency Managers").exists():
            agency = user.profile.agency
            if agency:
                queryset = queryset.filter(agency=agency, is_active=True)
                logger.debug(
                    f"User is an Agency Manager. Filtering shifts for agency: {agency}"
                )
            else:
                queryset = Shift.objects.none()
                logger.warning(
                    f"Agency Manager {user.username} does not have an associated agency."
                )
        elif user.groups.filter(name="Agency Staff").exists():
            agency = user.profile.agency
            if agency:
                queryset = queryset.filter(agency=agency, is_active=True)
                logger.debug(
                    f"User is Agency Staff. Filtering shifts for agency: {agency}"
                )
            else:
                queryset = Shift.objects.none()
                logger.warning(
                    f"Agency Staff {user.username} does not have an associated agency."
                )
        else:
            queryset = Shift.objects.none()
            logger.debug(
                "User does not belong to a recognized group. No shifts accessible."
            )

        logger.debug(f"Filtered queryset count: {queryset.count()}")
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        shift = self.object
        user = self.request.user
        profile = user.profile if hasattr(user, "profile") else None

        # Calculate distance if coordinates available
        distance = None
        if (
            profile
            and profile.latitude
            and profile.longitude
            and shift.latitude
            and shift.longitude
        ):
            distance = haversine_distance(
                profile.latitude,
                profile.longitude,
                shift.latitude,
                shift.longitude,
                unit="miles",
            )

        # Assignment data
        shift.assignments_count = shift.assignments.filter(
            status=ShiftAssignment.CONFIRMED
        ).count()

        context["distance_to_shift"] = distance

        # Check assignment status for current user
        context["is_assigned"] = ShiftAssignment.objects.filter(
            shift=shift, worker=user
        ).exists()

        # Set permission flags
        context["can_book"] = (
            user.groups.filter(name="Agency Staff").exists()
            and not shift.is_full
            and not context["is_assigned"]
            and shift.is_active
        )
        context["can_unbook"] = (
            user.groups.filter(name="Agency Staff").exists()
            and context["is_assigned"]
        )
        context["can_edit"] = user.is_superuser or (
            user.groups.filter(name="Agency Managers").exists()
            and shift.agency == profile.agency
            if profile
            else False
        )

        # Management permissions
        is_manager = (
            user.is_superuser
            or user.groups.filter(name="Agency Managers").exists()
            or user.groups.filter(name="Agency Owners").exists()
        )

        if is_manager:
            context["assigned_workers"] = shift.assignments.all()
            context["can_assign_workers"] = True

            # Worker assignment data
            if user.is_superuser:
                available_workers = User.objects.filter(
                    groups__name="Agency Staff",
                    is_active=True,
                ).exclude(shift_assignments__shift=shift)
            else:
                available_workers = User.objects.filter(
                    profile__agency=shift.agency,
                    groups__name="Agency Staff",
                    is_active=True,
                ).exclude(shift_assignments__shift=shift)
            context["available_workers"] = available_workers

            # Worker assignment forms
            assign_forms = []
            for worker in available_workers:
                form = AssignWorkerForm(
                    shift=shift,
                    user=user,
                    worker=worker,
                )
                assign_forms.append({"worker": worker, "form": form})
            context["assign_forms"] = assign_forms
            context["role_choices"] = ShiftAssignment.ROLE_CHOICES
        else:
            context["assigned_workers"] = None
            context["can_assign_workers"] = False
            context["available_workers"] = None
            context["assign_forms"] = []
            context["role_choices"] = ShiftAssignment.ROLE_CHOICES

        # Add completion form if needed
        if (
            user.is_superuser
            or user.groups.filter(
                name__in=["Agency Managers", "Agency Owners", "Agency Staff"]
            ).exists()
        ):
            if not shift.is_completed and shift.is_active:
                context["form"] = ShiftCompletionForm()

        return context


class ShiftCreateView(
    LoginRequiredMixin,
    AgencyManagerRequiredMixin,
    SubscriptionRequiredMixin,
    FeatureRequiredMixin,
    SuccessMessageMixin,
    CreateView,
):
    """Create view for shifts with agency and subscription validation"""

    required_features = ["shift_management"]
    model = Shift
    form_class = ShiftForm
    template_name = "shifts/shift_form.html"
    success_url = reverse_lazy("shifts:shift_list")
    success_message = "Shift has been created successfully."

    def dispatch(self, request, *args, **kwargs):
        """Verify agency association before allowing shift creation"""
        if not request.user.is_superuser:
            if (
                not hasattr(request.user, "profile")
                or not request.user.profile.agency
            ):
                messages.error(
                    request, "You are not associated with any agency."
                )
                logger.warning(
                    f"User {request.user.username} attempted to create shift without an associated agency."
                )
                return redirect("accounts:profile")
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        shift = form.save(commit=False)
        if self.request.user.is_superuser:
            agency = form.cleaned_data.get("agency")
            shift.agency = agency
        else:
            agency = self.request.user.profile.agency
            shift.agency = agency

            # Verify shift limit compliance
            subscription = agency.subscription
            if subscription and subscription.plan.shift_limit is not None:
                current_time = timezone.now()
                current_month_start = current_time.replace(
                    day=1, hour=0, minute=0, second=0, microsecond=0
                )
                current_shift_count = Shift.objects.filter(
                    agency=agency, created_at__gte=current_month_start
                ).count()
                if current_shift_count >= subscription.plan.shift_limit:
                    messages.error(
                        self.request,
                        f"Your agency has reached the maximum number of shifts ({subscription.plan.shift_limit}) for this month. Please upgrade your subscription.",
                    )
                    logger.info(
                        f"Agency '{agency.name}' has reached the shift limit for the month."
                    )
                    return redirect("subscriptions:upgrade_subscription")

        # Generate unique shift code if needed
        if not shift.shift_code:
            shift.shift_code = generate_shift_code()

        shift.save()
        form.save_m2m()

        logger.info(
            f"Shift '{shift.name}' created by {self.request.user.username} for agency {agency.name}."
        )
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["GOOGLE_PLACES_API_KEY"] = settings.GOOGLE_PLACES_API_KEY
        context["form_title"] = "Create Shift"
        return context


class ShiftUpdateView(
    LoginRequiredMixin,
    AgencyManagerRequiredMixin,
    SubscriptionRequiredMixin,
    FeatureRequiredMixin,
    SuccessMessageMixin,
    UpdateView,
):
    """Update view for shifts with role-based access controls"""

    required_features = ["shift_management"]
    model = Shift
    form_class = ShiftForm
    template_name = "shifts/shift_form.html"
    success_url = reverse_lazy("shifts:shift_list")
    success_message = "Shift has been updated successfully."

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        shift = form.save(commit=False)
        if self.request.user.is_superuser:
            agency = form.cleaned_data.get("agency")
            if agency:
                shift.agency = agency
        else:
            shift.agency = self.request.user.profile.agency

        shift.save()
        form.save_m2m()

        logger.info(
            f"Shift '{shift.name}' updated by {self.request.user.username}."
        )
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form_title"] = "Update Shift"
        context["GOOGLE_PLACES_API_KEY"] = settings.GOOGLE_PLACES_API_KEY
        return context


class ShiftDeleteView(
    LoginRequiredMixin,
    AgencyManagerRequiredMixin,
    SubscriptionRequiredMixin,
    FeatureRequiredMixin,
    SuccessMessageMixin,
    DeleteView,
):
    """Soft-delete implementation for shifts"""

    required_features = ["shift_management"]
    model = Shift
    template_name = "shifts/shift_confirm_delete.html"
    success_url = reverse_lazy("shifts:shift_list")
    success_message = "Shift deleted successfully."

    def delete(self, request, *args, **kwargs):
        shift = self.get_object()
        shift.is_active = False
        shift.save()
        logger.info(
            f"Shift '{shift.name}' deactivated by user {request.user.username}."
        )
        messages.success(request, self.success_message)
        return redirect(self.success_url)
