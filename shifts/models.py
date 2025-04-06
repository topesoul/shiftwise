# /workspace/shiftwise/shifts/models.py

import uuid

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils import timezone

from shifts.validators import validate_image

User = get_user_model()


class TimestampedModel(models.Model):
    """Abstract base model with creation and update timestamps"""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Shift(TimestampedModel):
    """Work shift entity managed by an agency"""

    # Shift Type Choices
    REGULAR = "regular"
    MORNING_SHIFT = "morning_shift"
    DAY_SHIFT = "day_shift"
    NIGHT_SHIFT = "night_shift"
    BANK_HOLIDAY = "bank_holiday"
    EMERGENCY_SHIFT = "emergency_shift"
    OVERTIME = "overtime"

    SHIFT_TYPE_CHOICES = [
        (REGULAR, "Regular"),
        (MORNING_SHIFT, "Morning Shift"),
        (DAY_SHIFT, "Day Shift"),
        (NIGHT_SHIFT, "Night Shift"),
        (BANK_HOLIDAY, "Bank Holiday"),
        (EMERGENCY_SHIFT, "Emergency Shift"),
        (OVERTIME, "Overtime"),
    ]

    # Shift Status Choices
    STATUS_PENDING = "pending"
    STATUS_COMPLETED = "completed"
    STATUS_CANCELED = "canceled"
    STATUS_OPEN = "open"
    STATUS_CLOSED = "closed"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_CANCELED, "Canceled"),
        (STATUS_OPEN, "Open"),
        (STATUS_CLOSED, "Closed"),
    ]

    # Shift Role Choices
    ROLE_CHOICES = (
        ("Staff", "Staff"),
        ("Manager", "Manager"),
        ("Admin", "Admin"),
        ("Care Worker", "Healthcare Worker"),
        ("Kitchen Staff", "Kitchen"),
        ("Front Office Staff", "Front Office"),
        ("Receptionist", "Receptionist"),
        ("Chef", "Chef"),
        ("Waiter", "Waiter"),
        ("Dishwasher", "Dishwasher"),
        ("Laundry Staff", "Laundry"),
        ("Housekeeping Staff", "Housekeeping"),
        ("Other", "Other"),
    )

    name = models.CharField(max_length=255)
    shift_code = models.CharField(
        max_length=100, unique=True, db_index=True, blank=True, null=True
    )
    shift_date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    end_date = models.DateField(
        help_text="Specify the date when the shift ends."
    )
    is_overnight = models.BooleanField(
        default=False, help_text="Indicates if shift spans into the next day."
    )
    capacity = models.PositiveIntegerField(default=1)
    agency = models.ForeignKey(
        "accounts.Agency", on_delete=models.CASCADE, related_name="shifts"
    )
    postcode = models.CharField(max_length=20, blank=True, null=True)
    address_line1 = models.CharField(max_length=255, blank=True, null=True)
    address_line2 = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    county = models.CharField(max_length=100, blank=True, null=True)
    country = models.CharField(max_length=100, default="UK")
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    shift_type = models.CharField(
        max_length=50, choices=SHIFT_TYPE_CHOICES, default=REGULAR
    )
    shift_role = models.CharField(
        max_length=100,
        choices=ROLE_CHOICES,
        default="Staff",
        help_text="Role required for this shift.",
    )
    hourly_rate = models.DecimalField(max_digits=10, decimal_places=2)
    notes = models.TextField(blank=True, null=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING
    )
    is_completed = models.BooleanField(default=False)
    completion_time = models.DateTimeField(null=True, blank=True)
    signature = models.ImageField(
        upload_to="signatures/",
        null=True,
        blank=True,
        validators=[validate_image],
    )
    duration = models.FloatField(null=True, blank=True)
    is_active = models.BooleanField(
        default=True, help_text="Determines availability for assignments."
    )

    class Meta:
        unique_together = ("agency", "shift_date", "name")
        ordering = ["shift_date", "start_time"]
        verbose_name = "Shift"
        verbose_name_plural = "Shifts"

    def __str__(self):
        return f"{self.name} on {self.shift_date}"

    def generate_shift_code(self):
        """
        Creates unique shift code (format: <AGENCY_CODE>-<UUID_SEGMENT>)
        Example: AG-1A2B3C
        """
        unique_segment = uuid.uuid4().hex[:6].upper()
        return f"{self.agency.agency_code}-{unique_segment}"

    def clean(self, skip_date_validation=False):
        """
        Validates shift data and calculates duration
        - Enforces date/time logic and 24-hour max duration
        - Handles overnight shifts appropriately
        """
        super().clean()

        # Check for prior field-level validation
        form_validated_date = (
            hasattr(self, "_date_validated") and self._date_validated
        )
        form_validated_end_date = (
            hasattr(self, "_end_date_validated") and self._end_date_validated
        )

        # Ensure shift date is not in the past unless skipping validation or already validated
        if not skip_date_validation and not form_validated_date:
            if self.shift_date and self.shift_date < timezone.now().date():
                raise ValidationError("Shift date cannot be in the past.")

        # Ensure all date and time fields are provided
        if not self.shift_date:
            raise ValidationError("Shift date must be provided.")

        if not self.end_date:
            raise ValidationError("End date must be provided.")

        if not self.start_time:
            raise ValidationError("Start time must be provided.")

        if not self.end_time:
            raise ValidationError("End time must be provided.")

        # Ensure end date is not before shift date (unless already validated by form)
        if (
            not form_validated_end_date
            and self.end_date
            and self.shift_date
            and self.end_date < self.shift_date
        ):
            raise ValidationError("End date cannot be before shift date.")

        # Combine start and end datetime objects
        start_dt = timezone.make_aware(
            timezone.datetime.combine(self.shift_date, self.start_time),
            timezone.get_current_timezone(),
        )
        end_dt = timezone.make_aware(
            timezone.datetime.combine(self.end_date, self.end_time),
            timezone.get_current_timezone(),
        )

        # Handle overnight shifts
        if self.is_overnight:
            if end_dt <= start_dt:
                end_dt += timezone.timedelta(days=1)
        else:
            # Non-overnight shifts: end_dt should be after start_dt
            if end_dt <= start_dt:
                raise ValidationError(
                    "End time must be after start time for non-overnight shifts."
                )

        # Calculate duration in hours
        duration = (end_dt - start_dt).total_seconds() / 3600

        # Validate duration does not exceed 24 hours
        if duration > 24:
            raise ValidationError("Shift duration cannot exceed 24 hours.")

        self.duration = duration

    def save(self, *args, **kwargs):
        """
        Manages shift_code generation and validation before saving
        """
        # Generate shift_code if missing and agency is set
        if not self.shift_code and self.agency:
            self.shift_code = self.generate_shift_code()
        elif not self.shift_code and not self.agency:
            import logging

            logger = logging.getLogger(__name__)
            logger.warning(
                "Shift saved without agency; shift_code generation skipped."
            )

        # Handle validation skipping options
        skip_validation = kwargs.pop("skip_validation", False)
        if not skip_validation:
            skip_date_validation = kwargs.pop("skip_date_validation", False)
            self.clean(skip_date_validation=skip_date_validation)

        super().save(*args, **kwargs)

        # Ensure shift_code is generated if agency was assigned during save
        if not self.shift_code and self.agency:
            self.shift_code = self.generate_shift_code()
            type(self).objects.filter(pk=self.pk).update(
                shift_code=self.shift_code
            )

    def get_absolute_url(self):
        """URL for shift detail view"""
        return reverse("shifts:shift_detail", kwargs={"pk": self.pk})

    @property
    def available_slots(self):
        """Number of remaining assignment slots"""
        assigned_count = self.assignments.filter(
            status=ShiftAssignment.CONFIRMED
        ).count()
        return self.capacity - assigned_count

    @property
    def is_full(self):
        """Checks if all capacity slots are filled"""
        return self.available_slots <= 0


class ShiftAssignment(TimestampedModel):
    """
    Links workers to shifts within their agency
    Enforces cross-agency assignment restrictions
    """

    # Assignment Status Choices
    CONFIRMED = "confirmed"
    CANCELED = "canceled"

    STATUS_CHOICES = [
        (CONFIRMED, "Confirmed"),
        (CANCELED, "Canceled"),
    ]

    # Shift Role Choices
    ROLE_CHOICES = (
        ("Staff", "Staff"),
        ("Manager", "Manager"),
        ("Admin", "Admin"),
        ("Care Worker", "Healthcare Worker"),
        ("Kitchen Staff", "Kitchen"),
        ("Front Office Staff", "Front Office"),
        ("Receptionist", "Receptionist"),
        ("Chef", "Chef"),
        ("Waiter", "Waiter"),
        ("Dishwasher", "Dishwasher"),
        ("Laundry Staff", "Laundry"),
        ("Housekeeping Staff", "Housekeeping"),
        ("Other", "Other"),
    )

    # Attendance Status Choices
    ATTENDANCE_STATUS_CHOICES = (
        ("attended", "Attended"),
        ("late", "Late"),
        ("no_show", "No Show"),
    )

    worker = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="shift_assignments"
    )
    shift = models.ForeignKey(
        "Shift", on_delete=models.CASCADE, related_name="assignments"
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    role = models.CharField(
        max_length=100, default="Staff", choices=ROLE_CHOICES
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=CONFIRMED
    )
    attendance_status = models.CharField(
        max_length=20,
        choices=ATTENDANCE_STATUS_CHOICES,
        null=True,
        blank=True,
        help_text="Post-shift attendance record",
    )
    completion_latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    completion_longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    completion_time = models.DateTimeField(null=True, blank=True)
    signature = models.ImageField(
        upload_to="shift_signatures/",
        null=True,
        blank=True,
        validators=[validate_image],
    )

    class Meta:
        unique_together = ("worker", "shift")
        ordering = ["-assigned_at"]
        verbose_name = "Shift Assignment"
        verbose_name_plural = "Shift Assignments"

    def __str__(self):
        return f"{self.worker} assigned to {self.shift.name} on {self.shift.shift_date}"

    def clean(self):
        """
        Enforces assignment business rules:
        - Validates worker-agency relationship
        - Prevents cross-agency assignments
        - Enforces capacity limits
        """
        super().clean()

        # Ensure worker's profile has an agency
        if (
            not hasattr(self.worker, "profile")
            or not self.worker.profile.agency
        ):
            raise ValidationError(
                "Worker must be associated with an agency to be assigned to a shift."
            )

        # Enforce agency isolation - workers can only be assigned to shifts within their agency
        if self.shift.agency != self.worker.profile.agency:
            raise ValidationError(
                f"Worker {self.worker.get_full_name()} belongs to {self.worker.profile.agency.name} agency, but this shift belongs to {self.shift.agency.name}. Cross-agency assignments are not allowed."
            )

        # Check capacity constraints for confirmed assignments
        if self.shift.is_full and self.status == self.CONFIRMED:
            raise ValidationError(
                "Cannot confirm assignment. The shift is already full."
            )

    def save(self, *args, **kwargs):
        """
        Validates business rules before saving unless explicitly bypassed
        """
        bypass_validation = kwargs.pop("bypass_validation", False)
        if not bypass_validation:
            self.clean()
        super().save(*args, **kwargs)


class StaffPerformance(models.Model):
    """Performance metrics for staff on specific shifts"""

    STATUS_CHOICES = [
        ("Excellent", "Excellent"),
        ("Good", "Good"),
        ("Average", "Average"),
        ("Poor", "Poor"),
    ]

    worker = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="performances"
    )
    shift = models.ForeignKey(
        "Shift", on_delete=models.CASCADE, related_name="performances"
    )
    wellness_score = models.DecimalField(
        max_digits=5, decimal_places=2, help_text="Score between 0 and 100"
    )
    performance_rating = models.DecimalField(
        max_digits=3, decimal_places=1, help_text="Rating out of 5"
    )
    status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default="Average"
    )
    comments = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("worker", "shift")
        verbose_name = "Staff Performance"
        verbose_name_plural = "Staff Performances"

    def __str__(self):
        return (
            f"Performance of {self.worker.username} for Shift {self.shift.id}"
        )

    def clean(self):
        """
        Validates score ranges:
        - Wellness: 0-100
        - Performance: 0-5
        """
        super().clean()

        # Validate wellness_score
        if not (0 <= self.wellness_score <= 100):
            raise ValidationError("Wellness score must be between 0 and 100.")

        # Validate performance_rating
        if not (0 <= self.performance_rating <= 5):
            raise ValidationError(
                "Performance rating must be between 0 and 5."
            )
