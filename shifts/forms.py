# /workspace/shiftwise/shifts/forms.py

import re

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Column, Field, Layout, Row

from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator, MinLengthValidator
from django.utils import timezone
from django.utils.html import strip_tags

from accounts.models import Agency
from core.forms import AddressFormMixin
from shifts.models import Shift, ShiftAssignment, StaffPerformance
from shifts.validators import validate_image
from shiftwise.utils import geocode_address

User = get_user_model()


class ShiftForm(AddressFormMixin, forms.ModelForm):
    """
    Shift creation/editing form with location autocomplete and agency-specific handling.
    """

    honeypot = forms.CharField(
        required=False,
        widget=forms.HiddenInput(),
        label="Leave empty",
    )

    class Meta:
        model = Shift
        fields = [
            "name",
            "shift_date",
            "start_time",
            "end_time",
            "end_date",
            "is_overnight",
            "capacity",
            "shift_type",
            "shift_role",
            "hourly_rate",
            "notes",
            "agency",
            "is_active",
            # Address fields
            "address_line1",
            "address_line2",
            "city",
            "county",
            "country",
            "postcode",
            "latitude",
            "longitude",
        ]
        widgets = {
            # Shift Name Field widget
            "name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Enter shift name",
                    "id": "id_name",
                }
            ),
            # Date and Time Fields widgets
            "shift_date": forms.DateInput(
                attrs={
                    "type": "date",
                    "class": "form-control",
                    "placeholder": "Select shift date",
                    "id": "id_shift_date",
                }
            ),
            "end_date": forms.DateInput(
                attrs={
                    "type": "date",
                    "class": "form-control",
                    "placeholder": "Select end date",
                    "id": "id_end_date",
                }
            ),
            "start_time": forms.TimeInput(
                attrs={
                    "type": "time",
                    "class": "form-control",
                    "placeholder": "Select start time",
                    "id": "id_start_time",
                }
            ),
            "end_time": forms.TimeInput(
                attrs={
                    "type": "time",
                    "class": "form-control",
                    "placeholder": "Select end time",
                    "id": "id_end_time",
                }
            ),
            "shift_type": forms.Select(
                attrs={
                    "class": "form-control",
                    "id": "id_shift_type",
                }
            ),
            "shift_role": forms.Select(
                attrs={
                    "class": "form-control",
                    "id": "id_shift_role",
                }
            ),
            "agency": forms.Select(
                attrs={
                    "class": "form-control",
                    "id": "id_agency",
                }
            ),
            "is_active": forms.CheckboxInput(
                attrs={
                    "class": "form-check-input",
                    "id": "id_is_active",
                }
            ),
            # Address fields
            "address_line1": forms.TextInput(
                attrs={
                    "class": "form-control address-autocomplete",
                    "placeholder": "Enter address line 1",
                    "autocomplete": "address-line1",
                    "id": "id_address_line1",
                }
            ),
            "address_line2": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Enter address line 2",
                    "autocomplete": "address-line2",
                    "id": "id_address_line2",
                }
            ),
            "city": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Enter city",
                    "autocomplete": "address-level2",
                    "id": "id_city",
                }
            ),
            "county": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Enter county",
                    "autocomplete": "administrative-area",
                    "id": "id_county",
                }
            ),
            "country": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Enter country",
                    "readonly": "readonly",
                    "autocomplete": "country-name",
                    "id": "id_country",
                }
            ),
            "postcode": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Enter postcode",
                    "autocomplete": "postal-code",
                    "id": "id_postcode",
                }
            ),
            "latitude": forms.HiddenInput(
                attrs={
                    "id": "id_latitude",
                }
            ),
            "longitude": forms.HiddenInput(
                attrs={
                    "id": "id_longitude",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super(ShiftForm, self).__init__(*args, **kwargs)

        # Add read-only shift code field for existing shifts
        if self.instance.pk and self.instance.shift_code:
            self.fields["shift_code_display"] = forms.CharField(
                required=False,
                disabled=True,
                initial=self.instance.shift_code,
                label="Shift Code",
                help_text="System-generated unique identifier for this shift.",
            )

        # Initialize FormHelper for crispy_forms
        self.helper = FormHelper()
        self.helper.form_method = "post"

        # Build layout based on whether this is a new or existing shift
        layout_fields = []

        if self.instance.pk and self.instance.shift_code:
            layout_fields.append(
                Row(
                    Column("name", css_class="form-group col-md-6 mb-0"),
                    Column("shift_code_display", css_class="form-group col-md-6 mb-0"),
                )
            )
        else:
            layout_fields.append(
                Row(
                    Column("name", css_class="form-group col-md-12 mb-0"),
                )
            )

        layout_fields.extend(
            [
                Row(
                    Column("shift_date", css_class="form-group col-md-6 mb-0"),
                    Column("end_date", css_class="form-group col-md-6 mb-0"),
                ),
                Row(
                    Column("start_time", css_class="form-group col-md-6 mb-0"),
                    Column("end_time", css_class="form-group col-md-6 mb-0"),
                ),
                Row(
                    Column("is_overnight", css_class="form-group col-md-6 mb-0"),
                    Column("capacity", css_class="form-group col-md-6 mb-0"),
                ),
                Row(
                    Column("hourly_rate", css_class="form-group col-md-6 mb-0"),
                    Column("shift_type", css_class="form-group col-md-6 mb-0"),
                ),
                Row(
                    Column("shift_role", css_class="form-group col-md-6 mb-0"),
                    Column("agency", css_class="form-group col-md-6 mb-0"),
                ),
                "notes",
                "is_active",
                "address_line1",
                "address_line2",
                Row(
                    Column("city", css_class="form-group col-md-4 mb-0"),
                    Column("county", css_class="form-group col-md-4 mb-0"),
                    Column("postcode", css_class="form-group col-md-4 mb-0"),
                ),
                "country",
                # Hidden fields
                Field("latitude"),
                Field("longitude"),
            ]
        )

        self.helper.layout = Layout(*layout_fields)

        # Handle agency and active status fields based on user permissions
        if self.user and self.user.is_superuser:
            self.fields["agency"].required = True
            self.fields["is_active"].required = False
        else:
            self.fields["agency"].widget = forms.HiddenInput()
            self.fields["agency"].required = False
            self.fields["is_active"].widget = forms.HiddenInput()
            self.fields["is_active"].required = False

        # Apply form-control class to fields without it
        for field_name, field in self.fields.items():
            if "class" not in field.widget.attrs:
                field.widget.attrs["class"] = "form-control"

    def clean_honeypot(self):
        """Spam prevention"""
        value = self.cleaned_data.get("honeypot", "")
        if value:
            raise forms.ValidationError("Spam check failed.")
        return value

    def clean_notes(self):
        """Prevent XSS in notes field"""
        notes = self.cleaned_data.get("notes", "")
        return strip_tags(notes)

    def clean(self):
        cleaned_data = super().clean()

        # Permission verification
        if self.user and not (self.user.is_superuser or self.user.has_perm("shifts.change_shift")):
            if self.instance.pk:
                raise ValidationError("You don't have permission to modify this shift")

        # Validate shift timing and capacity
        shift_date = cleaned_data.get("shift_date")
        end_date = cleaned_data.get("end_date")
        capacity = cleaned_data.get("capacity")
        hourly_rate = cleaned_data.get("hourly_rate")
        start_time = cleaned_data.get("start_time")
        end_time = cleaned_data.get("end_time")
        is_overnight = cleaned_data.get("is_overnight")

        # Date validation
        if shift_date and shift_date < timezone.now().date():
            self.add_error("shift_date", "Shift date cannot be in the past.")
            self._date_validated = True

        # End date validation
        if end_date and shift_date and end_date < shift_date:
            self.add_error("end_date", "End date cannot be before shift date.")
            self._end_date_validated = True

        # Capacity validation
        if capacity and capacity < 1:
            self.add_error("capacity", "Capacity must be at least 1.")

        # Hourly rate validation
        if hourly_rate and hourly_rate <= 0:
            self.add_error("hourly_rate", "Hourly rate must be positive.")

        # Start/end time validation
        if start_time and end_time:
            if not is_overnight and start_time >= end_time:
                self.add_error(
                    "end_time",
                    "End time must be after start time if the shift is not overnight.",
                )
            elif is_overnight and start_time == end_time:
                self.add_error(
                    "end_time",
                    "End time cannot be the same as start time for an overnight shift.",
                )

        return cleaned_data

    def clean_postcode(self):
        """UK postcode validation"""
        postcode = self.cleaned_data.get("postcode")
        if postcode:
            postcode = postcode.strip()
        else:
            postcode = ""

        if not postcode:
            return postcode

        uk_postcode_regex = r"^[A-Z]{1,2}\d[A-Z\d]? ?\d[A-Z]{2}$"
        if not re.match(uk_postcode_regex, postcode.upper()):
            raise ValidationError("Enter a valid UK postcode.")
        return postcode.upper()

    def clean_latitude(self):
        """Coordinate validation"""
        latitude = self.cleaned_data.get("latitude")
        if latitude is None:
            return latitude
        try:
            latitude = float(latitude)
        except ValueError:
            raise ValidationError("Invalid latitude value.")
        if not (-90 <= latitude <= 90):
            raise ValidationError("Latitude must be between -90 and 90.")
        return latitude

    def clean_longitude(self):
        """Coordinate validation"""
        longitude = self.cleaned_data.get("longitude")
        if longitude is None:
            return longitude
        try:
            longitude = float(longitude)
        except ValueError:
            raise ValidationError("Invalid longitude value.")
        if not (-180 <= longitude <= 180):
            raise ValidationError("Longitude must be between -180 and 180.")
        return longitude

    def save(self, commit=True):
        """Handle shift code generation and agency assignment"""
        shift = super().save(commit=False)

        # Set agency if not assigned
        if self.user and not self.user.is_superuser:
            if hasattr(self.user, "profile") and hasattr(self.user.profile, "agency") and self.user.profile.agency:
                shift.agency = self.user.profile.agency
            else:
                raise ValidationError("User does not have an associated agency.")
        
        # Generate shift code for new shifts
        if commit and not shift.shift_code and shift.agency:
            shift.shift_code = shift.generate_shift_code()
            
        if commit:
            shift.save(skip_validation=True)
            self.save_m2m()
        return shift


class ShiftFilterForm(forms.Form):
    """
    Shift search and filter form with date, status, location and keyword filtering.
    """

    honeypot = forms.CharField(
        required=False,
        widget=forms.HiddenInput(),
        label="Leave empty",
    )

    STATUS_CHOICES = [
        ("all", "All"),
        ("available", "Available"),
        ("booked", "Booked"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]

    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(
            attrs={"type": "date", "class": "form-control", "id": "id_date_from"}
        ),
        label="Date From",
    )
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control", "id": "id_date_to"}),
        label="Date To",
    )
    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={"class": "form-control", "id": "id_status"}),
        label="Status",
    )
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={
                "placeholder": "Search by name, agency, or shift type",
                "class": "form-control",
                "id": "id_search",
            }
        ),
        label="Search",
    )
    shift_code = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={
                "placeholder": "Search by shift code",
                "class": "form-control",
                "id": "id_shift_code",
            }
        ),
        label="Shift Code",
    )
    address = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={
                "placeholder": "Search by address",
                "class": "form-control address-autocomplete",
                "id": "id_address",
            }
        ),
        label="Address",
    )

    latitude = forms.FloatField(
        required=False,
        widget=forms.HiddenInput(attrs={"id": "id_latitude"}),
    )
    longitude = forms.FloatField(
        required=False,
        widget=forms.HiddenInput(attrs={"id": "id_longitude"}),
    )

    def __init__(self, *args, **kwargs):
        super(ShiftFilterForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = "get"
        self.helper.layout = Layout(
            Row(
                Column("date_from", css_class="form-group col-md-3 mb-0"),
                Column("date_to", css_class="form-group col-md-3 mb-0"),
                Column("status", css_class="form-group col-md-3 mb-0"),
                Column("search", css_class="form-group col-md-3 mb-0"),
            ),
            Row(
                Column("shift_code", css_class="form-group col-md-3 mb-0"),
                Column("address", css_class="form-group col-md-9 mb-0"),
            ),
            # Hidden fields
            Field("latitude"),
            Field("longitude"),
        )

    def clean_honeypot(self):
        """Spam prevention"""
        value = self.cleaned_data.get("honeypot", "")
        if value:
            raise ValidationError("Spam check failed.")
        return value

    def clean_search(self):
        """XSS prevention"""
        search = self.cleaned_data.get("search", "")
        return strip_tags(search)

    def clean_shift_code(self):
        """Sanitize shift code input"""
        shift_code = self.cleaned_data.get("shift_code", "")
        return strip_tags(shift_code)

    def clean_address(self):
        """Sanitize address input"""
        address = self.cleaned_data.get("address", "")
        return strip_tags(address)


class ShiftCompletionForm(forms.Form):
    """
    Captures digital signature, geolocation, and attendance status when completing shifts.
    """

    honeypot = forms.CharField(
        required=False,
        widget=forms.HiddenInput(),
        label="Leave empty",
    )

    signature = forms.CharField(widget=forms.HiddenInput(), required=False)
    latitude = forms.DecimalField(
        widget=forms.HiddenInput(attrs={"id": "id_shift_completion_latitude"}),
        max_digits=9,
        decimal_places=6,
        required=False,
    )
    longitude = forms.DecimalField(
        widget=forms.HiddenInput(attrs={"id": "id_shift_completion_longitude"}),
        max_digits=9,
        decimal_places=6,
        required=False,
    )
    attendance_status = forms.ChoiceField(
        choices=ShiftAssignment.ATTENDANCE_STATUS_CHOICES,
        widget=forms.RadioSelect,
        required=True,
        help_text="Select attendance status after completing the shift.",
    )

    class Meta:
        pass

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = "post"
        self.helper.layout = Layout(
            "signature",
            "latitude",
            "longitude",
            Row(
                Column("attendance_status", css_class="form-group col-md-12 mb-0"),
            ),
        )

    def clean_honeypot(self):
        """Spam prevention"""
        value = self.cleaned_data.get("honeypot", "")
        if value:
            raise ValidationError("Spam check failed.")
        return value

    def clean_signature(self):
        """Validate signature data URL format"""
        signature = self.cleaned_data.get("signature", "")
        if signature:
            if not signature.startswith("data:image/"):
                raise ValidationError("Invalid signature format.")
        return signature

    def clean(self):
        cleaned_data = super().clean()
        signature = cleaned_data.get("signature")
        latitude = cleaned_data.get("latitude")
        longitude = cleaned_data.get("longitude")
        attendance_status = cleaned_data.get("attendance_status")

        # Signature format validation
        if signature:
            try:
                format, imgstr = signature.split(";base64,")
                ext = format.split("/")[-1]
            except Exception as e:
                raise ValidationError("Invalid signature data.")

        # Coordinate validation
        if (latitude is not None and longitude is None) or (
            latitude is None and longitude is not None
        ):
            raise ValidationError("Both latitude and longitude must be provided together.")

        # Status validation
        if attendance_status not in dict(ShiftAssignment.ATTENDANCE_STATUS_CHOICES).keys():
            raise ValidationError("Invalid attendance status selected.")

        return cleaned_data


class StaffPerformanceForm(forms.ModelForm):
    """
    Records worker performance metrics and supervisor feedback after shift completion.
    """

    class Meta:
        model = StaffPerformance
        fields = ["wellness_score", "performance_rating", "status", "comments"]
        widgets = {
            "wellness_score": forms.NumberInput(
                attrs={"class": "form-control", "id": "id_wellness_score"}
            ),
            "performance_rating": forms.NumberInput(
                attrs={"class": "form-control", "id": "id_performance_rating"}
            ),
            "status": forms.Select(attrs={"class": "form-control", "id": "id_status"}),
            "comments": forms.Textarea(
                attrs={"class": "form-control", "rows": 4, "id": "id_comments"}
            ),
        }

    def clean_wellness_score(self):
        score = self.cleaned_data.get("wellness_score")
        if score < 0 or score > 100:
            raise ValidationError("Wellness score must be between 0 and 100.")
        return score

    def clean_performance_rating(self):
        rating = self.cleaned_data.get("performance_rating")
        if rating < 0 or rating > 5:
            raise ValidationError("Performance rating must be between 0 and 5.")
        return rating

    def clean_comments(self):
        """XSS prevention"""
        comments = self.cleaned_data.get("comments", "")
        return strip_tags(comments)


class AssignWorkerForm(forms.Form):
    """
    Assigns workers to shifts with role specification and permission controls.
    """

    honeypot = forms.CharField(
        required=False,
        widget=forms.HiddenInput(),
        label="Leave empty",
    )

    worker = forms.ModelChoiceField(
        queryset=User.objects.none(),
        widget=forms.HiddenInput(),
        required=True,
    )
    role = forms.ChoiceField(
        choices=ShiftAssignment.ROLE_CHOICES,
        required=True,
        widget=forms.Select(attrs={"class": "form-control", "id": "id_role"}),
        label="Role",
    )

    def __init__(self, *args, **kwargs):
        shift = kwargs.pop("shift", None)
        self.user = kwargs.pop("user", None)
        worker = kwargs.pop("worker", None)
        super().__init__(*args, **kwargs)

        if shift and self.user:
            if self.user.is_superuser:
                # Superusers can assign any active Agency Staff
                self.fields["worker"].queryset = User.objects.filter(
                    groups__name="Agency Staff",
                    is_active=True,
                ).exclude(shift_assignments__shift=shift)
            elif self.user.groups.filter(name="Agency Managers").exists():
                # Agency Managers limited to their agency staff
                self.fields["worker"].queryset = User.objects.filter(
                    profile__agency=shift.agency,
                    groups__name="Agency Staff",
                    is_active=True,
                ).exclude(shift_assignments__shift=shift)
            else:
                self.fields["worker"].queryset = User.objects.none()

        # Pre-set worker if provided
        if worker:
            self.fields["worker"].initial = worker.id

    def clean_honeypot(self):
        """Spam prevention"""
        value = self.cleaned_data.get("honeypot", "")
        if value:
            raise ValidationError("Spam check failed.")
        return value

    def clean(self):
        cleaned_data = super().clean()
        # Permission check
        if self.user and not (
            self.user.is_superuser or self.user.has_perm("shifts.add_shiftassignment")
        ):
            raise ValidationError("You don't have permission to assign workers to shifts")
        return cleaned_data


class UnassignWorkerForm(forms.Form):
    """
    Removes worker assignments from shifts.
    """

    honeypot = forms.CharField(
        required=False,
        widget=forms.HiddenInput(),
        label="Leave empty",
    )

    worker_id = forms.IntegerField(widget=forms.HiddenInput(attrs={"id": "id_worker_id"}))

    def clean_honeypot(self):
        """Spam prevention"""
        value = self.cleaned_data.get("honeypot", "")
        if value:
            raise ValidationError("Spam check failed.")
        return value
