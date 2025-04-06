# /workspace/shiftwise/shifts/views/staff_views.py

import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import Group
from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import Count, ExpressionWrapper, F, FloatField, Q, Sum
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from accounts.forms import StaffCreationForm, StaffUpdateForm
from core.mixins import AgencyManagerRequiredMixin, FeatureRequiredMixin, SubscriptionRequiredMixin
from shifts.models import Shift

# Initialize logger
logger = logging.getLogger(__name__)

User = get_user_model()


class StaffListView(
    LoginRequiredMixin,
    AgencyManagerRequiredMixin,
    SubscriptionRequiredMixin,
    FeatureRequiredMixin,
    ListView,
):
    """
    Displays a list of staff members.
    Only accessible to users with 'custom_integrations' feature.
    """

    required_features = ["custom_integrations"]
    model = User
    template_name = "shifts/staff_list.html"
    context_object_name = "staff_members"
    paginate_by = 20

    def get_queryset(self):
        user = self.request.user
        agency = user.profile.agency if not user.is_superuser else None
        search_query = self.request.GET.get("search", "")
        status_filter = self.request.GET.get("status", "")
        date_from = self.request.GET.get("date_from", "")
        date_to = self.request.GET.get("date_to", "")

        # Base queryset filtering Agency Staff and active users
        staff_members = User.objects.filter(groups__name="Agency Staff", is_active=True)

        if not user.is_superuser and agency:
            staff_members = staff_members.filter(profile__agency=agency)

        # Annotate with shift statistics
        staff_members = staff_members.annotate(
            total_shifts=Count("shift_assignments"),
            completed_shifts=Count(
                "shift_assignments",
                filter=Q(shift_assignments__shift__status=Shift.STATUS_COMPLETED),
            ),
            pending_shifts=Count(
                "shift_assignments",
                filter=Q(shift_assignments__shift__status=Shift.STATUS_PENDING),
            ),
            total_hours=Sum(
                "shift_assignments__shift__duration",
                filter=Q(shift_assignments__shift__status=Shift.STATUS_COMPLETED),
            ),
            total_pay=Sum(
                ExpressionWrapper(
                    F("shift_assignments__shift__duration")
                    * F("shift_assignments__shift__hourly_rate"),
                    output_field=FloatField(),
                ),
                filter=Q(shift_assignments__shift__status=Shift.STATUS_COMPLETED),
            ),
        )

        # Apply search filter
        if search_query:
            staff_members = staff_members.filter(
                Q(username__icontains=search_query)
                | Q(first_name__icontains=search_query)
                | Q(last_name__icontains=search_query)
                | Q(email__icontains=search_query)
            )

        # Apply shift status filter
        if status_filter:
            staff_members = staff_members.filter(
                shift_assignments__shift__status=status_filter,
            ).distinct()

        # Apply date range filter
        if date_from and date_to:
            staff_members = staff_members.filter(
                shift_assignments__shift__shift_date__range=[date_from, date_to]
            ).distinct()

        # Order the queryset by username
        staff_members = staff_members.order_by("username")

        return staff_members

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["search_query"] = self.request.GET.get("search", "")
        context["status_filter"] = self.request.GET.get("status", "")
        context["date_from"] = self.request.GET.get("date_from", "")
        context["date_to"] = self.request.GET.get("date_to", "")
        return context


class StaffCreateView(
    LoginRequiredMixin,
    AgencyManagerRequiredMixin,
    SubscriptionRequiredMixin,
    FeatureRequiredMixin,
    SuccessMessageMixin,
    CreateView,
):
    """
    Allows agency managers and superusers to add new staff members to their agency.
    Superusers can add staff to any agency.
    """

    required_features = ["custom_integrations"]
    model = User
    form_class = StaffCreationForm
    template_name = "shifts/add_staff.html"
    success_url = reverse_lazy("shifts:staff_list")
    success_message = "Staff member has been added successfully."

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update({"request": self.request})  # Pass request to form
        return kwargs

    def form_valid(self, form):
        user = form.save(commit=False)

        # Generate a random password for the new user
        from core.utils import generate_random_password, send_notification_email

        raw_password = generate_random_password()
        user.set_password(raw_password)

        # Determine agency for the user
        agency = None
        if not self.request.user.is_superuser:
            agency = self.request.user.profile.agency
            if not agency:
                from core.mixins import handle_permission_error

                logger.warning(
                    f"User {self.request.user.username} attempted to add staff without an associated agency."
                )
                return handle_permission_error(
                    self.request,
                    "You must be associated with an agency to add staff members.",
                    "accounts:profile",
                )
            user.save()
            user.profile.agency = agency
            user.profile.travel_radius = form.cleaned_data.get("travel_radius") or 0.0
            user.profile.save()
        else:
            agency = form.cleaned_data.get("agency")
            user.save()

        # Add to 'Agency Staff' group
        agency_staff_group, _ = Group.objects.get_or_create(name="Agency Staff")
        user.groups.add(agency_staff_group)

        # Send email notification to the new user
        from django.contrib.sites.shortcuts import get_current_site
        from django.urls import reverse

        current_site = get_current_site(self.request)
        login_url = f"https://{current_site.domain}{reverse('accounts:login_view')}"

        email_context = {
            "user": user,
            "password": raw_password,
            "created_by": self.request.user.get_full_name() or self.request.user.username,
            "login_url": login_url,
            "agency": agency,
        }

        email_sent = send_notification_email(
            to_email=user.email,
            subject="Your New ShiftWise Account",
            template_path="accounts/emails/new_staff_account.txt",
            context=email_context,
        )

        if email_sent:
            messages.success(
                self.request,
                f"Staff member added successfully and notification email sent to {user.email}.",
            )
        else:
            messages.warning(
                self.request,
                f"Staff member added successfully but notification email could not be sent to {user.email}. "
                f"Please provide them with their username ({user.username}) and temporary password manually.",
            )

        logger.info(f"Staff member {user.username} added by {self.request.user.username}.")
        return super().form_valid(form)


class StaffUpdateView(
    LoginRequiredMixin,
    AgencyManagerRequiredMixin,
    SubscriptionRequiredMixin,
    FeatureRequiredMixin,
    SuccessMessageMixin,
    UpdateView,
):
    """
    Allows agency managers or superusers to edit staff details.
    Superusers can edit any staff member regardless of agency association.
    """

    required_features = ["custom_integrations"]
    model = User
    form_class = StaffUpdateForm
    template_name = "shifts/edit_staff.html"
    success_url = reverse_lazy("shifts:staff_list")
    success_message = "Staff details have been updated successfully."

    def dispatch(self, request, *args, **kwargs):
        """
        Ensure that non-superusers can only edit staff within their agency.
        """
        user = self.request.user
        staff_member = self.get_object()
        if not user.is_superuser:
            if staff_member.profile.agency != user.profile.agency:
                from core.mixins import handle_permission_error

                return handle_permission_error(
                    request,
                    "You do not have permission to edit this staff member.",
                    "shifts:staff_list",
                )
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        from core.utils import send_notification_email

        # Capture the changed fields for the notification
        changed_fields = []
        if form.has_changed():
            changed_fields = [
                form.fields[field].label or field.replace("_", " ").title()
                for field in form.changed_data
            ]

        user = form.save()

        # Send email notification about the update
        if changed_fields:
            email_context = {
                "user": user,
                "updated_by": self.request.user.get_full_name() or self.request.user.username,
                "updated_fields": changed_fields,
            }

            email_sent = send_notification_email(
                to_email=user.email,
                subject="Your ShiftWise Account Has Been Updated",
                template_path="accounts/emails/user_updated.txt",
                context=email_context,
            )

            if email_sent:
                messages.success(
                    self.request,
                    f"Staff member updated successfully and notification email sent to {user.email}.",
                )
            else:
                messages.warning(
                    self.request,
                    f"Staff member updated successfully but notification email could not be sent to {user.email}.",
                )

        logger.info(f"Staff member {user.username} updated by {self.request.user.username}.")
        return super().form_valid(form)


class StaffDeleteView(
    LoginRequiredMixin,
    AgencyManagerRequiredMixin,
    SubscriptionRequiredMixin,
    FeatureRequiredMixin,
    SuccessMessageMixin,
    DeleteView,
):
    """
    Allows agency managers or superusers to deactivate a staff member.
    Superusers can deactivate any staff member regardless of agency association.
    """

    required_features = ["custom_integrations"]
    model = User
    template_name = "shifts/delete_staff.html"
    success_url = reverse_lazy("shifts:staff_list")
    success_message = "Staff member has been deactivated successfully."

    def dispatch(self, request, *args, **kwargs):
        """
        Ensure that non-superusers can only deactivate staff within their agency.
        """
        user = self.request.user
        staff_member = self.get_object()
        if not user.is_superuser:
            if staff_member.profile.agency != user.profile.agency:
                from core.mixins import handle_permission_error

                return handle_permission_error(
                    request,
                    "You do not have permission to deactivate this staff member.",
                    "shifts:staff_list",
                )
        return super().dispatch(request, *args, **kwargs)

    def delete(self, request, *args, **kwargs):
        from core.utils import send_notification_email

        staff_member = self.get_object()
        staff_member.is_active = False
        staff_member.save()

        # Send email notification about the deactivation
        email_context = {
            "user": staff_member,
            "deactivated_by": request.user.get_full_name() or request.user.username,
        }

        email_sent = send_notification_email(
            to_email=staff_member.email,
            subject="Your ShiftWise Account Has Been Deactivated",
            template_path="accounts/emails/user_deactivated.txt",
            context=email_context,
        )

        if email_sent:
            messages.success(
                request,
                f'Staff member "{staff_member.username}" has been deactivated successfully '
                f"and notification email sent to {staff_member.email}.",
            )
        else:
            messages.warning(
                request,
                f'Staff member "{staff_member.username}" has been deactivated successfully '
                f"but notification email could not be sent to {staff_member.email}.",
            )

        logger.info(
            f"Staff member {staff_member.username} deactivated by user {request.user.username}."
        )
        return redirect(self.success_url)
