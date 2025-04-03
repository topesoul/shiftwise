# /workspace/shiftwise/shifts/utils.py

from .models import ShiftAssignment


def is_shift_full(shift):
    return ShiftAssignment.objects.filter(shift=shift).count() >= shift.capacity


def is_user_assigned(shift, user):
    return ShiftAssignment.objects.filter(shift=shift, worker=user).exists()


def can_complete_shift(user, shift):
    """
    Determines if a user can complete a specific shift.
    Returns (boolean, message) tuple.
    """
    if shift.is_completed:
        return False, "This shift has already been completed."
    
    if user.is_superuser:
        return True, ""
        
    if not ShiftAssignment.objects.filter(shift=shift, worker=user).exists():
        return False, "You are not assigned to this shift."
        
    if not hasattr(user, "profile") or not user.profile.agency:
        return False, "Your profile is not associated with any agency."
        
    if shift.agency != user.profile.agency:
        return False, "You can only complete shifts within your agency."
        
    return True, ""
