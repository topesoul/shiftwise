# /workspace/shiftwise/shifts/views/assignment_views.py

import logging

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views import View

from core.mixins import AgencyManagerRequiredMixin, FeatureRequiredMixin
from shifts.forms import AssignWorkerForm
from shifts.models import Shift, ShiftAssignment, User
from core.utils import ajax_response_with_message

# Initialize logger
logger = logging.getLogger(__name__)


class AssignWorkerView(
    LoginRequiredMixin, AgencyManagerRequiredMixin, FeatureRequiredMixin, View
):
    """
    Assigns a worker to a specific shift.
    Handles POST requests from the Shift Detail page.
    """

    required_features = ["shift_management"]

    def post(self, request, shift_id, *args, **kwargs):
        user = request.user
        shift = get_object_or_404(Shift, id=shift_id, is_active=True)

        # Check if this is an AJAX request
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

        # Extract worker ID and role from POST data
        worker_id = request.POST.get("worker")
        role = request.POST.get("role") or "Staff"  # Default role

        if not worker_id:
            if is_ajax:
                return ajax_response_with_message(False, "Worker field is required to assign.")
            else:
                messages.error(request, "Worker field is required to assign.")
                return redirect("shifts:shift_detail", pk=shift.id)

        worker = get_object_or_404(User, id=worker_id)

        # Permission check: Ensure worker belongs to the same agency
        if not user.is_superuser and worker.profile.agency != shift.agency:
            if is_ajax:
                return ajax_response_with_message(False, "You cannot assign workers from a different agency.")
            else:
                messages.error(request, "You cannot assign workers from a different agency.")
                return redirect("shifts:shift_detail", pk=shift.id)

        # Check if the shift is already full
        if shift.is_full:
            if is_ajax:
                return ajax_response_with_message(False, "Cannot assign worker. The shift is already full.")
            else:
                messages.error(request, "Cannot assign worker. The shift is already full.")
                return redirect("shifts:shift_detail", pk=shift.id)

        # Check if the worker is already assigned to the shift
        if ShiftAssignment.objects.filter(shift=shift, worker=worker).exists():
            if is_ajax:
                return ajax_response_with_message(False, f"Worker {worker.get_full_name()} is already assigned to this shift.")
            else:
                messages.error(request, f"Worker {worker.get_full_name()} is already assigned to this shift.")
                return redirect("shifts:shift_detail", pk=shift.id)

        # Validate role
        if role not in dict(ShiftAssignment.ROLE_CHOICES).keys():
            if is_ajax:
                return ajax_response_with_message(False, "Invalid role selected.")
            else:
                messages.error(request, "Invalid role selected.")
                return redirect("shifts:shift_detail", pk=shift.id)

        # Create the ShiftAssignment
        try:
            ShiftAssignment.objects.create(
                shift=shift, worker=worker, role=role, status=ShiftAssignment.CONFIRMED
            )
            
            success_message = f"Worker {worker.get_full_name()} has been successfully assigned to the shift with role '{role}'."
            
            if is_ajax:
                return ajax_response_with_message(
                    True, 
                    success_message,
                    {'redirect': reverse('shifts:shift_detail', kwargs={'pk': shift.id})}
                )
            else:
                messages.success(request, success_message)
                logger.info(f"Worker {worker.username} assigned to shift {shift.id} with role '{role}' by {user.username}.")
                return redirect("shifts:shift_detail", pk=shift.id)
                
        except Exception as e:
            if is_ajax:
                return ajax_response_with_message(False, "An unexpected error occurred while assigning the worker.")
            else:
                messages.error(request, "An unexpected error occurred while assigning the worker.")
                logger.exception(f"Unexpected error when assigning worker: {e}")
                return redirect("shifts:shift_detail", pk=shift.id)


class UnassignWorkerView(
    LoginRequiredMixin, AgencyManagerRequiredMixin, FeatureRequiredMixin, View
):
    """
    Allows agency managers or superusers to unassign a worker from a specific shift.
    Handles POST requests from the Shift Detail page.
    """

    required_features = ["shift_management"]

    def post(self, request, shift_id, assignment_id, *args, **kwargs):
        user = request.user
        shift = get_object_or_404(Shift, id=shift_id, is_active=True)
        assignment = get_object_or_404(ShiftAssignment, id=assignment_id, shift=shift)

        # Permission Checks
        if not user.is_superuser:
            if shift.agency != user.profile.agency:
                messages.error(
                    request,
                    "You do not have permission to unassign workers from this shift.",
                )
                logger.warning(
                    f"User {user.username} attempted to unassign worker from shift {shift.id} outside their agency."
                )
                return redirect("shifts:shift_detail", pk=shift_id)

        # Perform Unassignment
        try:
            worker_full_name = assignment.worker.get_full_name()
            assignment.delete()
            messages.success(
                request,
                f"Worker {worker_full_name} has been unassigned from the shift.",
            )
            logger.info(
                f"Worker {assignment.worker.username} unassigned from shift {shift.id} by {user.username}."
            )
        except Exception as e:
            messages.error(
                request,
                "An error occurred while unassigning the worker. Please try again.",
            )
            logger.exception(
                f"Error unassigning worker {assignment.worker.username} from shift {shift.id}: {e}"
            )
            return redirect("shifts:shift_detail", pk=shift_id)

        return redirect("shifts:shift_detail", pk=shift_id)
