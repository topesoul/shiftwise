# /workspace/shiftwise/shifts/views/completion_views.py

import base64
import logging
import uuid

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.generic import View

from core.mixins import AgencyManagerRequiredMixin, FeatureRequiredMixin, SubscriptionRequiredMixin
from core.utils import ajax_response_with_message
from shifts.forms import ShiftCompletionForm
from shifts.models import Shift, ShiftAssignment
from shiftwise.utils import haversine_distance

logger = logging.getLogger(__name__)

User = get_user_model()


def can_complete_shift(user, shift):
    if user.is_superuser or ShiftAssignment.objects.filter(shift=shift, worker=user).exists():
        return True, ""
    return False, "You are not allowed to complete this shift."


class ShiftCompleteView(
    LoginRequiredMixin,
    SubscriptionRequiredMixin,
    FeatureRequiredMixin,
    View,
):
    """
    Shift completion view with signature capture and location verification.
    Restricted to assigned workers and superusers.
    """

    required_features = ["shift_management"]

    def get(self, request, shift_id, *args, **kwargs):
        shift = get_object_or_404(Shift, id=shift_id, is_active=True)

        # Verify assignment authorization
        if not (
            request.user.is_superuser
            or ShiftAssignment.objects.filter(shift=shift, worker=request.user).exists()
        ):
            messages.error(request, "You are not assigned to this shift.")
            return redirect("shifts:shift_detail", pk=shift.id)

        if shift.is_completed:
            messages.info(request, "This shift has already been completed.")
            return redirect("shifts:shift_detail", pk=shift.id)

        form = ShiftCompletionForm()
        context = {
            "form": form,
            "shift": shift,
        }
        return render(request, "shifts/shift_complete_modal.html", context)

    def post(self, request, shift_id, *args, **kwargs):
        shift = get_object_or_404(Shift, id=shift_id, is_active=True)
        user = request.user

        # Prevent completion of future shifts
        if shift.shift_date > timezone.now().date():
            messages.error(request, "Cannot complete a shift scheduled in the future.")
            return redirect("shifts:shift_detail", pk=shift.id)

        can_complete, message = can_complete_shift(user, shift)
        if not can_complete:
            messages.error(request, message)
            return redirect("shifts:shift_detail", pk=shift.id)

        form = ShiftCompletionForm(request.POST, request.FILES)
        if form.is_valid():
            signature_data = form.cleaned_data.get("signature")
            latitude = form.cleaned_data.get("latitude")
            longitude = form.cleaned_data.get("longitude")
            attendance_status = form.cleaned_data.get("attendance_status")

            # Process signature data
            if signature_data:
                try:
                    format, imgstr = signature_data.split(";base64,")
                    ext = format.split("/")[-1]
                    data = ContentFile(
                        base64.b64decode(imgstr),
                        name=f"shift_{shift.id}_signature_{uuid.uuid4()}.{ext}",
                    )
                except Exception as e:
                    logger.exception(f"Error processing signature for Shift ID {shift.id}: {e}")
                    messages.error(request, "Invalid signature data.")
                    return redirect("shifts:shift_detail", pk=shift.id)
            else:
                data = None

            # Verify location proximity for non-superusers
            if not user.is_superuser:
                if latitude and longitude and shift.latitude and shift.longitude:
                    try:
                        user_lat = float(latitude)
                        user_lon = float(longitude)
                        shift_lat = float(shift.latitude)
                        shift_lon = float(shift.longitude)

                        distance = haversine_distance(
                            user_lat,
                            user_lon,
                            shift_lat,
                            shift_lon,
                            unit="miles",
                        )

                    except (ValueError, TypeError) as e:
                        logger.exception(f"Invalid geolocation data for Shift ID {shift.id}: {e}")
                        messages.error(request, "Invalid location data.")
                        return redirect("shifts:shift_detail", pk=shift.id)

                    if distance > 0.5:
                        messages.error(
                            request,
                            f"You are too far from the shift location ({distance:.2f} miles).",
                        )
                        return redirect("shifts:shift_detail", pk=shift.id)

            # Create or retrieve assignment record
            try:
                if user.is_superuser:
                    try:
                        assignment = ShiftAssignment.objects.get(shift=shift, worker=user)
                    except ShiftAssignment.DoesNotExist:
                        assignment = ShiftAssignment(shift=shift, worker=user)
                        assignment.save(bypass_validation=True)
                else:
                    assignment, created = ShiftAssignment.objects.get_or_create(
                        shift=shift, worker=user
                    )
            except ValidationError as ve:
                messages.error(request, str(ve))
                return redirect("shifts:shift_detail", pk=shift.id)

            # Verify agency associations
            if not user.profile.agency:
                messages.error(request, "Your profile is not associated with any agency.")
                return redirect("accounts:profile")

            if shift.agency != user.profile.agency:
                messages.error(request, "You can only complete shifts within your agency.")
                return redirect("shifts:shift_detail", pk=shift.id)

            # Update assignment completion data
            if data:
                assignment.signature = data
            if latitude and longitude:
                assignment.completion_latitude = latitude
                assignment.completion_longitude = longitude
            assignment.completion_time = timezone.now()

            if attendance_status:
                assignment.attendance_status = attendance_status

            # Update shift completion status if all assignments complete
            all_assignments = ShiftAssignment.objects.filter(shift=shift)
            if all(a.completion_time for a in all_assignments):
                shift.is_completed = True
                shift.completion_time = timezone.now()
                if data:
                    shift.signature = data

            # Persist changes
            try:
                shift.clean(skip_date_validation=True)
                shift.save()
                if user.is_superuser:
                    assignment.save(bypass_validation=True)
                else:
                    assignment.save()
            except ValidationError as ve:
                messages.error(request, str(ve))
                return redirect("shifts:shift_detail", pk=shift.id)

            messages.success(request, "Shift completed successfully.")
            logger.info(f"User {request.user.username} completed Shift ID {shift_id}.")
            return redirect("shifts:shift_detail", pk=shift.id)
        else:
            messages.error(request, "Please correct the errors below.")
            return redirect("shifts:shift_detail", pk=shift.id)


class ShiftCompleteForUserView(
    LoginRequiredMixin,
    SubscriptionRequiredMixin,
    FeatureRequiredMixin,
    View,
):
    """
    Administrative view allowing authorized users to complete shifts on behalf of workers.
    Limited to superusers, agency managers, and owners.
    """

    required_features = ["shift_management"]

    def dispatch(self, request, *args, **kwargs):
        if not (
            request.user.is_superuser
            or request.user.groups.filter(name__in=["Agency Managers", "Agency Owners"]).exists()
        ):
            messages.error(request, "You don't have permission to complete shifts for other users.")
            return redirect("shifts:shift_list")
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, shift_id, user_id, *args, **kwargs):
        shift = get_object_or_404(Shift, id=shift_id, is_active=True)
        user_to_complete = get_object_or_404(User, id=user_id, is_active=True)

        # Verify user role eligibility
        is_valid_user = (
            user_to_complete.groups.filter(name="Agency Staff").exists()
            or user_to_complete.is_superuser
        )

        if not is_valid_user:
            messages.error(
                request,
                f"User {user_to_complete.get_full_name()} cannot have shifts completed on their behalf because they are not Agency Staff.",
            )
            return redirect("shifts:shift_detail", pk=shift.id)

        # Verify agency permissions
        if not request.user.is_superuser and shift.agency != request.user.profile.agency:
            messages.error(request, "You cannot complete shifts outside your agency.")
            return redirect("shifts:shift_detail", pk=shift.id)

        if user_to_complete.profile.agency != shift.agency:
            messages.error(request, "The worker does not belong to the same agency as the shift.")
            return redirect("shifts:shift_detail", pk=shift.id)

        if shift.is_completed:
            messages.info(request, "This shift has already been completed.")
            return redirect("shifts:shift_detail", pk=shift.id)

        form = ShiftCompletionForm()
        context = {
            "form": form,
            "shift": shift,
            "user_to_complete": user_to_complete,
        }
        return render(request, "shifts/shift_complete_for_user_modal.html", context)

    def post(self, request, shift_id, user_id, *args, **kwargs):
        shift = get_object_or_404(Shift, id=shift_id, is_active=True)
        user = request.user
        user_to_complete = get_object_or_404(User, id=user_id, is_active=True)

        # Verify worker eligibility
        is_valid_user = (
            user_to_complete.groups.filter(name="Agency Staff").exists()
            or user_to_complete.is_superuser
        )

        if not is_valid_user:
            messages.error(
                request,
                f"User {user_to_complete.get_full_name()} cannot have shifts completed on their behalf because they are not Agency Staff.",
            )
            return redirect("shifts:shift_detail", pk=shift.id)

        # Agency permission checks
        if not request.user.is_superuser and shift.agency != request.user.profile.agency:
            messages.error(request, "You cannot complete shifts outside your agency.")
            logger.warning(
                f"User {request.user.username} attempted to complete Shift ID {shift.id} outside their agency."
            )
            return redirect("shifts:shift_detail", pk=shift.id)

        if user_to_complete.profile.agency != shift.agency:
            messages.error(request, "The worker does not belong to the same agency as the shift.")
            return redirect("shifts:shift_detail", pk=shift.id)

        if shift.is_completed:
            messages.info(request, "This shift has already been completed.")
            return redirect("shifts:shift_detail", pk=shift.id)

        form = ShiftCompletionForm(request.POST, request.FILES)
        if form.is_valid():
            signature_data = form.cleaned_data.get("signature")
            latitude = form.cleaned_data.get("latitude")
            longitude = form.cleaned_data.get("longitude")
            attendance_status = form.cleaned_data.get("attendance_status")

            # Process signature
            if signature_data:
                try:
                    format, imgstr = signature_data.split(";base64,")
                    ext = format.split("/")[-1]
                    data = ContentFile(
                        base64.b64decode(imgstr),
                        name=f"shift_{shift.id}_signature_{uuid.uuid4()}.{ext}",
                    )
                except Exception as e:
                    logger.exception(f"Error processing signature for Shift ID {shift.id}: {e}")
                    messages.error(request, "Invalid signature data.")
                    return redirect("shifts:shift_detail", pk=shift.id)
            else:
                data = None

            # Use shift location for privileged users when coordinates not provided
            if (
                request.user.is_superuser
                or request.user.groups.filter(name="Agency Managers").exists()
            ):
                if not latitude or not longitude:
                    latitude = shift.latitude
                    longitude = shift.longitude

            # Proximity validation for non-superusers
            if not request.user.is_superuser:
                if latitude and longitude and shift.latitude and shift.longitude:
                    try:
                        user_lat = float(latitude)
                        user_lon = float(longitude)
                        shift_lat = float(shift.latitude)
                        shift_lon = float(shift.longitude)

                        distance = haversine_distance(
                            user_lat,
                            user_lon,
                            shift_lat,
                            shift_lon,
                            unit="miles",
                        )

                    except (ValueError, TypeError) as e:
                        logger.exception(f"Invalid geolocation data for Shift ID {shift.id}: {e}")
                        messages.error(request, "Invalid location data.")
                        return redirect("shifts:shift_detail", pk=shift.id)

                    if distance > 0.5:
                        messages.error(
                            request,
                            f"You are too far from the shift location ({distance:.2f} miles).",
                        )
                        return redirect("shifts:shift_detail", pk=shift.id)

            # Create or retrieve assignment
            assignment, created = ShiftAssignment.objects.get_or_create(
                shift=shift, worker=user_to_complete
            )

            # Update completion data
            if data:
                assignment.signature = data
            if latitude and longitude:
                assignment.completion_latitude = latitude
                assignment.completion_longitude = longitude
            assignment.completion_time = timezone.now()

            if attendance_status:
                assignment.attendance_status = attendance_status

            # Update shift completion status if all assignments complete
            all_assignments = ShiftAssignment.objects.filter(shift=shift)
            if all(a.completion_time for a in all_assignments):
                shift.is_completed = True
                shift.completion_time = timezone.now()
                if data:
                    shift.signature = data

            # Save changes
            try:
                shift.clean(skip_date_validation=True)
                shift.save()
                assignment.save(bypass_validation=True)
            except ValidationError as ve:
                messages.error(request, ve.message)
                return redirect("shifts:shift_detail", pk=shift.id)

            messages.success(
                request,
                f"Shift '{shift.name}' completed successfully for {user_to_complete.get_full_name()}.",
            )
            logger.info(
                f"Shift ID {shift.id} completed by {request.user.username} for user {user_to_complete.username}."
            )
            return redirect("shifts:shift_detail", pk=shift.id)
        else:
            messages.error(request, "Please correct the errors below.")
            return redirect("shifts:shift_detail", pk=shift.id)


class ShiftCompleteAjaxView(
    LoginRequiredMixin,
    AgencyManagerRequiredMixin,
    SubscriptionRequiredMixin,
    FeatureRequiredMixin,
    View,
):
    """
    AJAX endpoint for shift completion with JSON responses.
    Accessible to superusers and agency managers.
    """

    required_features = ["shift_management"]

    def post(self, request, shift_id, *args, **kwargs):
        user = request.user
        shift = get_object_or_404(Shift, id=shift_id, is_active=True)

        # Permission check
        if not (
            ShiftAssignment.objects.filter(shift=shift, worker=user).exists() or user.is_superuser
        ):
            return ajax_response_with_message(
                False,
                "You do not have permission to complete this shift.",
                {"redirect": reverse("shifts:shift_detail", kwargs={"pk": shift_id})},
            )

        if shift.is_completed:
            return ajax_response_with_message(False, "This shift has already been completed.")

        signature = request.POST.get("signature")
        latitude = request.POST.get("latitude")
        longitude = request.POST.get("longitude")
        attendance_status = request.POST.get("attendance_status")

        # Process signature
        if signature:
            try:
                format, imgstr = signature.split(";base64,")
                ext = format.split("/")[-1]
                data = ContentFile(
                    base64.b64decode(imgstr),
                    name=f"shift_{shift.id}_signature_{uuid.uuid4()}.{ext}",
                )
            except Exception as e:
                logger.exception(
                    f"Error decoding signature from user {user.username} for Shift ID {shift_id}: {e}"
                )
                return ajax_response_with_message(False, "Invalid signature data.")
        else:
            data = None

        # Proximity validation for non-superusers
        if not user.is_superuser:
            if latitude and longitude and shift.latitude and shift.longitude:
                try:
                    user_lat = float(latitude)
                    user_lon = float(longitude)
                    shift_lat = float(shift.latitude)
                    shift_lon = float(shift.longitude)

                    distance = haversine_distance(
                        user_lat, user_lon, shift_lat, shift_lon, unit="miles"
                    )

                except (ValueError, TypeError):
                    return ajax_response_with_message(False, "Invalid location data.")

                if distance > 0.5:
                    return ajax_response_with_message(
                        False,
                        f"You are not within the required 0.5-mile distance to complete this shift. Current distance: {distance:.2f} miles.",
                    )

        # Update shift data
        if data:
            shift.signature = data

        shift.is_completed = True
        shift.completion_time = timezone.now()

        # Update assignment data
        try:
            if not user.is_superuser:
                assignment = ShiftAssignment.objects.get(shift=shift, worker=user)
                if data:
                    assignment.signature = data
                if latitude and longitude:
                    assignment.completion_latitude = latitude
                    assignment.completion_longitude = longitude
                assignment.completion_time = timezone.now()
                if attendance_status:
                    assignment.attendance_status = attendance_status
                assignment.save()
        except ShiftAssignment.DoesNotExist:
            logger.error(
                f"ShiftAssignment does not exist for user {user.username} and shift {shift.id}."
            )
            return ajax_response_with_message(False, "Shift assignment not found.")
        except Exception as e:
            logger.exception(
                f"Error updating ShiftAssignment for user {user.username} and shift {shift.id}: {e}"
            )
            return ajax_response_with_message(
                False, "An error occurred while completing the shift."
            )

        # Verify all assignments are complete
        all_assignments = ShiftAssignment.objects.filter(shift=shift)
        if all(a.completion_time for a in all_assignments):
            shift.is_completed = True
            shift.completion_time = timezone.now()
            if data:
                shift.signature = data
            shift.save()

        # Save changes
        try:
            shift.clean(skip_date_validation=True)
            shift.save()
        except ValidationError as ve:
            return ajax_response_with_message(False, ve.message)

        logger.info(f"User {user.username} completed Shift ID {shift_id} via AJAX.")
        return ajax_response_with_message(
            True,
            "Shift completed successfully.",
            {"redirect": reverse("shifts:shift_detail", kwargs={"pk": shift_id})},
        )

    def get(self, request, shift_id, *args, **kwargs):
        return ajax_response_with_message(False, "Invalid request method.")
