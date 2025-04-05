# /workspace/shiftwise/shifts/views/assignment_views.py

import logging

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View

from core.mixins import AgencyManagerRequiredMixin, FeatureRequiredMixin
from shifts.forms import AssignWorkerForm
from shifts.models import Shift, ShiftAssignment, User
from core.utils import ajax_response_with_message

logger = logging.getLogger(__name__)


class AssignWorkerView(
    LoginRequiredMixin, AgencyManagerRequiredMixin, FeatureRequiredMixin, View
):
    """
    Handles worker assignment to shifts via POST requests.
    Supports both AJAX and standard form submissions.
    """

    required_features = ["shift_management"]

    def post(self, request, shift_id, *args, **kwargs):
        user = request.user
        shift = get_object_or_404(Shift, id=shift_id, is_active=True)

        # Determine request type for appropriate response handling
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

        worker_id = request.POST.get("worker")
        role = request.POST.get("role") or "Staff"  # Default role

        if not worker_id:
            if is_ajax:
                return ajax_response_with_message(False, "Worker field is required to assign.")
            else:
                messages.error(request, "Worker field is required to assign.")
                return redirect("shifts:shift_detail", pk=shift.id)

        worker = get_object_or_404(User, id=worker_id)

        # Verify worker belongs to the shift's agency - business rule
        if worker.profile.agency != shift.agency:
            if is_ajax:
                return ajax_response_with_message(False, 
                    f"Worker {worker.get_full_name()} belongs to {worker.profile.agency.name} agency, but this shift belongs to {shift.agency.name} agency. Cross-agency assignments are not allowed.")
            else:
                messages.error(request, 
                    f"Worker {worker.get_full_name()} belongs to {worker.profile.agency.name} agency, but this shift belongs to {shift.agency.name} agency. Cross-agency assignments are not allowed.")
                return redirect("shifts:shift_detail", pk=shift.id)

        # Shift capacity validation
        if shift.is_full:
            if is_ajax:
                return ajax_response_with_message(False, "Cannot assign worker. The shift is already full.")
            else:
                messages.error(request, "Cannot assign worker. The shift is already full.")
                return redirect("shifts:shift_detail", pk=shift.id)

        # Prevent duplicate assignments
        if ShiftAssignment.objects.filter(shift=shift, worker=worker).exists():
            if is_ajax:
                return ajax_response_with_message(False, f"Worker {worker.get_full_name()} is already assigned to this shift.")
            else:
                messages.error(request, f"Worker {worker.get_full_name()} is already assigned to this shift.")
                return redirect("shifts:shift_detail", pk=shift.id)

        # Validate role selection
        if role not in dict(ShiftAssignment.ROLE_CHOICES).keys():
            if is_ajax:
                return ajax_response_with_message(False, "Invalid role selected.")
            else:
                messages.error(request, "Invalid role selected.")
                return redirect("shifts:shift_detail", pk=shift.id)

        # Process assignment creation
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
            error_message = f"Error assigning worker: {str(e)}"
            logger.exception(f"Unexpected error when assigning worker {worker.id} to shift {shift.id}: {e}")
            
            if is_ajax:
                return ajax_response_with_message(False, error_message)
            else:
                messages.error(request, error_message)
                return redirect("shifts:shift_detail", pk=shift.id)


class UnassignWorkerView(
    LoginRequiredMixin, AgencyManagerRequiredMixin, FeatureRequiredMixin, View
):
    """
    Manages worker removal from shifts with confirmation step.
    Restricted to agency managers for shifts within their agency.
    """

    required_features = ["shift_management"]
    
    def get(self, request, shift_id, assignment_id, *args, **kwargs):
        user = request.user
        shift = get_object_or_404(Shift, id=shift_id, is_active=True)
        assignment = get_object_or_404(ShiftAssignment, id=assignment_id, shift=shift)
        
        # Agency permission boundary enforcement
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
                
        return render(request, "shifts/unassign_worker_confirm.html", {
            "shift": shift,
            "assignment": assignment
        })

    def post(self, request, shift_id, assignment_id, *args, **kwargs):
        user = request.user
        shift = get_object_or_404(Shift, id=shift_id, is_active=True)
        assignment = get_object_or_404(ShiftAssignment, id=assignment_id, shift=shift)

        # Agency permission boundary enforcement
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
