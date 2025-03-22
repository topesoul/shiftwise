# /workspace/shiftwise/accounts/forms.py

import logging
import re
from decimal import Decimal, InvalidOperation

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Column, Field, Layout, Row
from django import forms
from django.contrib.auth import get_user_model, login
from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from PIL import Image, ImageOps

from core.constants import AGENCY_TYPE_CHOICES, ROLE_CHOICES
from core.forms import AddressFormMixin
from core.utils import assign_user_to_group, generate_unique_code
from shiftwise.utils import geocode_address

from .models import Agency, Invitation, Profile

User = get_user_model()

# Initialize the logger
logger = logging.getLogger(__name__)


class AgencyForm(AddressFormMixin, forms.ModelForm):
    """
    Form for creating and updating Agency instances.
    Integrates Google Places Autocomplete for address fields.
    """

    class Meta:
        model = Agency
        fields = [
            "name",
            "agency_type",
            "email",
            "phone_number",
            "website",
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
            "name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Enter agency name",
                    "id": "id_name",
                }
            ),
            "agency_type": forms.Select(
                attrs={
                    "class": "form-control",
                    "id": "id_agency_type",
                }
            ),
            "email": forms.EmailInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Agency email",
                    "id": "id_email",
                }
            ),
            "phone_number": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Phone Number",
                    "id": "id_phone_number",
                }
            ),
            "website": forms.URLInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Website URL",
                    "id": "id_website",
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
        super(AgencyForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = "post"
        self.helper.layout = Layout(
            "name",
            "agency_type",
            "address_line1",
            "address_line2",
            Row(
                Column("city", css_class="form-group col-md-4 mb-0"),
                Column("county", css_class="form-group col-md-4 mb-0"),
                Column("postcode", css_class="form-group col-md-4 mb-0"),
            ),
            "country",
            "email",
            "phone_number",
            "website",
            # Hidden fields
            Field("latitude"),
            Field("longitude"),
        )

    def clean_email(self):
        """Ensures the email is valid and not already in use."""
        email = (self.cleaned_data.get("email") or "").strip().lower()
        if not email:
            raise ValidationError("Email is required.")
        
        # Validate email format
        try:
            forms.EmailField().clean(email)
        except ValidationError:
            raise ValidationError("Enter a valid email address.")
            
        # Check if email already exists, excluding current instance
        existing_users = User.objects.filter(email=email)
        if self.instance.pk:
            existing_agencies = Agency.objects.filter(email=email).exclude(pk=self.instance.pk)
        else:
            existing_agencies = Agency.objects.filter(email=email)
            
        if existing_users.exists():
            raise ValidationError("This email is already in use by a user account.")
            
        if existing_agencies.exists():
            raise ValidationError("This email is already in use by another agency.")
            
        return email

    def clean_phone_number(self):
        """Validates the phone number format."""
        phone = self.cleaned_data.get("phone_number")
        if phone:
            # Remove spaces and non-numeric characters for validation
            phone_digits = re.sub(r'\D', '', phone)
            if len(phone_digits) < 10 or len(phone_digits) > 15:
                raise ValidationError("Phone number must be between 10 and 15 digits.")
        return phone

    def clean(self):
        """Validates the form fields together, including geocoding address."""
        cleaned_data = super().clean()
        address_line1 = cleaned_data.get("address_line1")
        city = cleaned_data.get("city")
        postcode = cleaned_data.get("postcode")
        
        # Require at least address_line1 or city and postcode
        if not address_line1 and not (city and postcode):
            self.add_error("address_line1", "Either address line 1 or city and postcode are required.")
            return cleaned_data
            
        # Construct the full address for geocoding
        address_components = [
            address_line1,
            cleaned_data.get("address_line2"),
            city,
            cleaned_data.get("county"),
            postcode,
            cleaned_data.get("country"),
        ]
        full_address = ", ".join(filter(None, address_components))

        if full_address.strip():
            try:
                geocode_result = geocode_address(full_address)
                if geocode_result:
                    cleaned_data["latitude"] = geocode_result["latitude"]
                    cleaned_data["longitude"] = geocode_result["longitude"]
                    logger.info(f"Geocoded address for agency: {full_address}")
                else:
                    # Handle case where geocoding returns no results but doesn't error
                    logger.warning(f"No geocoding results for address: {full_address}")
                    self.add_error(None, "We couldn't find the location for this address. Please check and try again.")
            except Exception as e:
                logger.error(f"Failed to geocode address for agency: {e}")
                # Don't add error, let form submit with manual coordinates if provided
                if not (cleaned_data.get("latitude") and cleaned_data.get("longitude")):
                    self.add_error(None, "Could not validate address location. You may continue without geolocation or try a different address.")
        
        return cleaned_data

    def save(self, commit=True):
        """
        Overrides the save method to correctly handle the agency attributes.
        """
        agency = super().save(commit=False)

        # Generate unique agency code if necessary
        if not agency.agency_code:
            agency.agency_code = generate_unique_code(prefix="AG-", length=8)

        if commit:
            agency.save()
            self.save_m2m()
        return agency


class AgencySignUpForm(AddressFormMixin, UserCreationForm):
    """
    Form for agency owners to create a new agency account.
    Collects both User and Agency information.
    """

    # Agency-specific fields
    agency_name = forms.CharField(
        max_length=100,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter agency name",
                "id": "id_agency_name",
            }
        ),
    )
    agency_type = forms.ChoiceField(
        choices=AGENCY_TYPE_CHOICES,
        required=True,
        widget=forms.Select(
            attrs={
                "class": "form-control",
                "id": "id_agency_type",
            }
        ),
    )
    agency_email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter agency email",
                "id": "id_agency_email",
            }
        ),
    )
    agency_phone_number = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter agency phone number",
                "id": "id_agency_phone_number",
            }
        ),
    )
    agency_website = forms.URLField(
        required=False,
        widget=forms.URLInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter agency website URL",
                "id": "id_agency_website",
            }
        ),
    )

    # Address fields
    address_line1 = forms.CharField(
        max_length=255,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control address-autocomplete",
                "placeholder": "Enter address line 1",
                "autocomplete": "address-line1",
                "id": "id_address_line1",
            }
        ),
    )
    address_line2 = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter address line 2",
                "autocomplete": "address-line2",
                "id": "id_address_line2",
            }
        ),
    )
    city = forms.CharField(
        max_length=100,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter city",
                "autocomplete": "address-level2",
                "id": "id_city",
            }
        ),
    )
    county = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter county",
                "autocomplete": "administrative-area",
                "id": "id_county",
            }
        ),
    )
    country = forms.CharField(
        max_length=100,
        required=True,
        initial="UK",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter country",
                "readonly": "readonly",
                "autocomplete": "country-name",
                "id": "id_country",
            }
        ),
    )
    postcode = forms.CharField(
        max_length=20,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter postcode",
                "autocomplete": "postal-code",
                "id": "id_postcode",
            }
        ),
    )
    latitude = forms.FloatField(
        required=False,
        widget=forms.HiddenInput(attrs={"id": "id_latitude"}),
    )
    longitude = forms.FloatField(
        required=False,
        widget=forms.HiddenInput(attrs={"id": "id_longitude"}),
    )
    travel_radius = forms.DecimalField(
        required=False,
        min_value=0,
        max_value=50,
        initial=0.0,
        help_text="Maximum travel distance in miles (0-50)",
        widget=forms.NumberInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter travel radius (in miles)",
                "id": "id_travel_radius",
                "min": "0",
                "max": "50",
                "step": "0.1",
            }
        ),
    )

    class Meta:
        model = User
        fields = (
            "username",
            "email",
            "password1",
            "password2",
            "first_name",
            "last_name",
        )
        widgets = {
            "username": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Enter username",
                    "id": "id_username",
                }
            ),
            "email": forms.EmailInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Enter your email",
                    "id": "id_email",
                }
            ),
            "password1": forms.PasswordInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Enter password",
                    "id": "id_password1",
                }
            ),
            "password2": forms.PasswordInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Confirm password",
                    "id": "id_password2",
                }
            ),
            "first_name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Enter your first name",
                    "id": "id_first_name",
                }
            ),
            "last_name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Enter your last name",
                    "id": "id_last_name",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super(AgencySignUpForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = "post"
        self.helper.layout = Layout(
            "username",
            "email",
            Row(
                Column("password1", css_class="form-group col-md-6 mb-0"),
                Column("password2", css_class="form-group col-md-6 mb-0"),
            ),
            Row(
                Column("first_name", css_class="form-group col-md-6 mb-0"),
                Column("last_name", css_class="form-group col-md-6 mb-0"),
            ),
            "agency_name",
            "agency_type",
            "address_line1",
            "address_line2",
            Row(
                Column("city", css_class="form-group col-md-4 mb-0"),
                Column("county", css_class="form-group col-md-4 mb-0"),
                Column("postcode", css_class="form-group col-md-4 mb-0"),
            ),
            "country",
            "agency_email",
            "agency_phone_number",
            "agency_website",
            "travel_radius",
            # Hidden fields
            Field("latitude"),
            Field("longitude"),
        )
        
        # Make first name and last name required
        self.fields["first_name"].required = True
        self.fields["last_name"].required = True

    def clean_email(self):
        """
        Ensures the email is valid, unique, and not already in use.
        """
        email = self.cleaned_data.get("email", "").strip().lower()
        if not email:
            raise ValidationError("Email is required.")
            
        try:
            forms.EmailField().clean(email)
        except ValidationError:
            raise ValidationError("Enter a valid email address.")
            
        if User.objects.filter(email=email).exists():
            raise ValidationError("A user with this email already exists.")
            
        return email

    def clean_agency_email(self):
        """
        Validates the agency email is unique and not already in use.
        """
        agency_email = self.cleaned_data.get("agency_email", "").strip().lower()
        if not agency_email:
            raise ValidationError("Agency email is required.")
            
        try:
            forms.EmailField().clean(agency_email)
        except ValidationError:
            raise ValidationError("Enter a valid email address for the agency.")
            
        if Agency.objects.filter(email=agency_email).exists():
            raise ValidationError("An agency with this email already exists.")
            
        return agency_email

    def clean_travel_radius(self):
        """
        Ensures that travel_radius is a valid decimal between 0 and 50.
        """
        travel_radius = self.cleaned_data.get("travel_radius")
        if travel_radius is None:
            return Decimal('0.0')
            
        try:
            travel_radius = Decimal(str(travel_radius))
            if travel_radius < 0 or travel_radius > 50:
                raise ValidationError("Travel radius must be between 0 and 50 miles.")
        except (InvalidOperation, TypeError, ValueError):
            raise ValidationError("Travel radius must be a valid number.")
            
        return travel_radius

    def clean_agency_phone_number(self):
        """Validates the agency phone number format."""
        phone = self.cleaned_data.get("agency_phone_number")
        if phone:
            # Remove spaces and non-numeric characters for validation
            phone_digits = re.sub(r'\D', '', phone)
            if len(phone_digits) < 10 or len(phone_digits) > 15:
                raise ValidationError("Phone number must be between 10 and 15 digits.")
        return phone

    def clean(self):
        """
        Validates the form as a whole, including address geocoding.
        """
        cleaned_data = super().clean()
        
        # Check if user email and agency email are different
        user_email = cleaned_data.get("email")
        agency_email = cleaned_data.get("agency_email")
        
        if user_email and agency_email and user_email == agency_email:
            self.add_error("agency_email", 
                          "Agency email must be different from your personal email.")
            
        # Validate address fields
        address_line1 = cleaned_data.get("address_line1")
        city = cleaned_data.get("city")
        postcode = cleaned_data.get("postcode")
        
        if not address_line1 or not city or not postcode:
            if not address_line1:
                self.add_error("address_line1", "Address line 1 is required.")
            if not city:
                self.add_error("city", "City is required.")
            if not postcode:
                self.add_error("postcode", "Postcode is required.")
            return cleaned_data
            
        # Attempt to geocode the address
        address_components = [
            address_line1,
            cleaned_data.get("address_line2"),
            city,
            cleaned_data.get("county"),
            postcode,
            cleaned_data.get("country"),
        ]
        full_address = ", ".join(filter(None, address_components))

        try:
            geocode_result = geocode_address(full_address)
            if geocode_result:
                cleaned_data["latitude"] = geocode_result["latitude"]
                cleaned_data["longitude"] = geocode_result["longitude"]
                logger.info(f"Geocoded address for agency signup: {full_address}")
            else:
                logger.warning(f"No geocoding results for address: {full_address}")
                self.add_error(None, "We couldn't find the location for this address. Please check and try again.")
        except Exception as e:
            logger.error(f"Failed to geocode address for agency signup: {e}")
            # Don't block form submission due to geocoding failure
            self.add_error(None, "Could not validate address location. You may continue without geolocation or try a different address.")
            
        return cleaned_data

    def save(self, commit=True):
        """
        Saves the User and Agency instances.
        """
        # Save User
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"].strip().lower()
        user.role = "agency_owner"

        if commit:
            user.save()
            # Assign user to 'Agency Owners' group
            assign_user_to_group(user, "Agency Owners")

            # Create Agency
            agency = Agency.objects.create(
                name=self.cleaned_data["agency_name"],
                agency_type=self.cleaned_data["agency_type"],
                postcode=self.cleaned_data.get("postcode"),
                address_line1=self.cleaned_data.get("address_line1"),
                address_line2=self.cleaned_data.get("address_line2"),
                city=self.cleaned_data.get("city"),
                county=self.cleaned_data.get("county"),
                country=self.cleaned_data.get("country") or "UK",
                email=self.cleaned_data["agency_email"],
                phone_number=self.cleaned_data.get("agency_phone_number"),
                website=self.cleaned_data.get("agency_website"),
                latitude=self.cleaned_data.get("latitude"),
                longitude=self.cleaned_data.get("longitude"),
                owner=user,
            )

            # Update Profile
            profile, created = Profile.objects.get_or_create(user=user)
            profile.agency = agency
            profile.address_line1 = self.cleaned_data.get("address_line1")
            profile.address_line2 = self.cleaned_data.get("address_line2")
            profile.city = self.cleaned_data.get("city")
            profile.county = self.cleaned_data.get("county")
            profile.country = self.cleaned_data.get("country") or "UK"
            profile.postcode = self.cleaned_data.get("postcode")
            profile.latitude = self.cleaned_data.get("latitude")
            profile.longitude = self.cleaned_data.get("longitude")
            profile.travel_radius = self.cleaned_data.get("travel_radius") or 0.0
            profile.save()

            # Log the creation
            logger.info(
                f"New agency owner created: {user.username}, Agency: {agency.name}"
            )

        return user


class SignUpForm(AddressFormMixin, UserCreationForm):
    """
    Form for users to sign up (primarily via invitation).
    """

    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter your email",
                "required": True,
                "id": "id_email",
            }
        ),
    )
    first_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter your first name",
                "id": "id_first_name",
            }
        ),
    )
    last_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter your last name",
                "id": "id_last_name",
            }
        ),
    )
    travel_radius = forms.DecimalField(
        required=False,
        min_value=0,
        max_value=50,
        initial=0.0,
        validators=[MinValueValidator(0), MaxValueValidator(50)],
        help_text="Maximum travel distance in miles (0-50)",
        widget=forms.NumberInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter travel radius (in miles)",
                "id": "id_travel_radius",
                "min": "0",
                "max": "50",
                "step": "0.1",
            }
        ),
    )

    # Address fields
    address_line1 = forms.CharField(
        max_length=255,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control address-autocomplete",
                "placeholder": "Enter address line 1",
                "autocomplete": "address-line1",
                "id": "id_address_line1",
            }
        ),
    )
    address_line2 = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter address line 2",
                "autocomplete": "address-line2",
                "id": "id_address_line2",
            }
        ),
    )
    city = forms.CharField(
        max_length=100,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter city",
                "autocomplete": "address-level2",
                "id": "id_city",
            }
        ),
    )
    county = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter county",
                "autocomplete": "administrative-area",
                "id": "id_county",
            }
        ),
    )
    country = forms.CharField(
        max_length=100,
        required=True,
        initial="UK",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter country",
                "readonly": "readonly",
                "autocomplete": "country-name",
                "id": "id_country",
            }
        ),
    )
    postcode = forms.CharField(
        max_length=20,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter postcode",
                "autocomplete": "postal-code",
                "id": "id_postcode",
            }
        ),
    )
    latitude = forms.FloatField(
        required=False,
        widget=forms.HiddenInput(attrs={"id": "id_latitude"}),
    )
    longitude = forms.FloatField(
        required=False,
        widget=forms.HiddenInput(attrs={"id": "id_longitude"}),
    )

    class Meta:
        model = User
        fields = (
            "username",
            "email",
            "password1",
            "password2",
            "first_name",
            "last_name",
        )
        widgets = {
            "username": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Enter username",
                    "id": "id_username",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        # Accept 'request' as a keyword argument to access the current user
        self.request = kwargs.pop("request", None)
        super(SignUpForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = "post"
        self.helper.layout = Layout(
            Row(
                Column("username", css_class="form-group col-md-6 mb-0"),
                Column("email", css_class="form-group col-md-6 mb-0"),
            ),
            Row(
                Column("password1", css_class="form-group col-md-6 mb-0"),
                Column("password2", css_class="form-group col-md-6 mb-0"),
            ),
            Row(
                Column("first_name", css_class="form-group col-md-6 mb-0"),
                Column("last_name", css_class="form-group col-md-6 mb-0"),
            ),
            "travel_radius",
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
        )

    def clean_email(self):
        """
        Ensures the email is valid and not already in use.
        """
        email = self.cleaned_data.get("email", "").strip().lower()
        if not email:
            raise ValidationError("Email is required.")
            
        try:
            forms.EmailField().clean(email)
        except ValidationError:
            raise ValidationError("Enter a valid email address.")
            
        if User.objects.filter(email=email).exists():
            raise ValidationError("A user with this email already exists.")
            
        return email

    def clean_travel_radius(self):
        """
        Ensures that travel_radius is a valid decimal between 0 and 50.
        """
        travel_radius = self.cleaned_data.get("travel_radius")
        if travel_radius is None:
            return Decimal('0.0')
            
        try:
            travel_radius = Decimal(str(travel_radius))
            if travel_radius < 0 or travel_radius > 50:
                raise ValidationError("Travel radius must be between 0 and 50 miles.")
        except (InvalidOperation, TypeError, ValueError):
            raise ValidationError("Travel radius must be a valid number.")
            
        return travel_radius

    def clean(self):
        """
        Validates the form as a whole, including address geocoding.
        """
        cleaned_data = super().clean()
        
        # Validate address fields
        address_line1 = cleaned_data.get("address_line1")
        city = cleaned_data.get("city")
        postcode = cleaned_data.get("postcode")
        
        if not address_line1 or not city or not postcode:
            if not address_line1:
                self.add_error("address_line1", "Address line 1 is required.")
            if not city:
                self.add_error("city", "City is required.")
            if not postcode:
                self.add_error("postcode", "Postcode is required.")
            return cleaned_data
            
        # Attempt to geocode the address
        address_components = [
            address_line1,
            cleaned_data.get("address_line2"),
            city,
            cleaned_data.get("county"),
            postcode,
            cleaned_data.get("country"),
        ]
        full_address = ", ".join(filter(None, address_components))

        try:
            geocode_result = geocode_address(full_address)
            if geocode_result:
                cleaned_data["latitude"] = geocode_result["latitude"]
                cleaned_data["longitude"] = geocode_result["longitude"]
                logger.info(f"Geocoded address for user signup: {full_address}")
            else:
                logger.warning(f"No geocoding results for address: {full_address}")
                self.add_error(None, "We couldn't find the location for this address. Please check and try again.")
        except Exception as e:
            logger.error(f"Failed to geocode address for user signup: {e}")
            # Don't block form submission due to geocoding failure
            self.add_error(None, "Could not validate address location. You may continue without geolocation or try a different address.")
            
        return cleaned_data

    def save(self, commit=True):
        """
        Saves the user and associates them with the 'Agency Staff' group and their agency.
        """
        user = super().save(commit=False)
        user.email = self.cleaned_data.get("email", "").strip().lower()
        user.role = "staff"

        if commit:
            user.save()
            # Assign user to 'Agency Staff' group
            assign_user_to_group(user, "Agency Staff")

            # Associate user with the agency if available
            if (
                self.request
                and hasattr(self.request.user, "profile")
                and self.request.user.profile.agency
            ):
                agency = self.request.user.profile.agency
                profile, created = Profile.objects.get_or_create(user=user)
                profile.agency = agency
                profile.travel_radius = self.cleaned_data.get("travel_radius") or 0.0
                profile.address_line1 = self.cleaned_data.get("address_line1")
                profile.address_line2 = self.cleaned_data.get("address_line2")
                profile.city = self.cleaned_data.get("city")
                profile.county = self.cleaned_data.get("county")
                profile.country = self.cleaned_data.get("country") or "UK"
                profile.postcode = self.cleaned_data.get("postcode")
                profile.latitude = self.cleaned_data.get("latitude")
                profile.longitude = self.cleaned_data.get("longitude")
                profile.save()
            else:
                profile, created = Profile.objects.get_or_create(user=user)
                profile.travel_radius = self.cleaned_data.get("travel_radius") or 0.0
                profile.address_line1 = self.cleaned_data.get("address_line1")
                profile.address_line2 = self.cleaned_data.get("address_line2")
                profile.city = self.cleaned_data.get("city")
                profile.county = self.cleaned_data.get("county")
                profile.country = self.cleaned_data.get("country") or "UK"
                profile.postcode = self.cleaned_data.get("postcode")
                profile.latitude = self.cleaned_data.get("latitude")
                profile.longitude = self.cleaned_data.get("longitude")
                profile.save()

            # Log the creation of a new user
            logger.info(f"New user created: {user.username}")

        return user


class InvitationForm(forms.ModelForm):
    """
    Form for agency managers to invite new staff members via email.
    Superusers can also select an agency.
    """

    class Meta:
        model = Invitation
        fields = ["email"]
        widgets = {
            "email": forms.EmailInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Enter staff email",
                    "required": True,
                    "id": "id_email",
                }
            ),
        }

    # Add agency field only if the user is a superuser
    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super(InvitationForm, self).__init__(*args, **kwargs)
        if user and user.is_superuser:
            self.fields["agency"] = forms.ModelChoiceField(
                queryset=Agency.objects.all(),
                required=False,
                widget=forms.Select(attrs={"class": "form-control", "id": "id_agency"}),
                help_text="Select an agency for the staff member. Leave blank if not applicable.",
            )
        else:
            # For non-superusers, associate with their own agency
            if hasattr(user, "profile") and user.profile.agency:
                self.initial["agency"] = user.profile.agency

        self.helper = FormHelper()
        self.helper.form_method = "post"
        self.helper.layout = Layout(
            "email",
            "agency",
        )

    def clean_email(self):
        """
        Validates the invitation email to prevent duplicates and existing users.
        """
        email = self.cleaned_data.get("email", "").strip().lower()
        if not email:
            raise ValidationError("Email is required.")
            
        try:
            forms.EmailField().clean(email)
        except ValidationError:
            raise ValidationError("Enter a valid email address.")
            
        if User.objects.filter(email=email).exists():
            raise ValidationError("A user with this email already exists.")
            
        active_invitation = Invitation.objects.filter(email=email, is_active=True).first()
        if active_invitation:
            # Check if invitation is expired
            if active_invitation.is_expired():
                # Deactivate expired invitation to allow creating a new one
                active_invitation.is_active = False
                active_invitation.save()
            else:
                raise ValidationError("An active invitation for this email already exists.")
                
        return email


class AcceptInvitationForm(UserCreationForm):
    """
    Form for invited staff members to accept their invitation and set up their account.
    """

    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(
            attrs={"class": "form-control", "readonly": "readonly", "id": "id_email"}
        ),
    )
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Choose a username",
                "id": "id_username",
            }
        ),
    )
    password1 = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter password",
                "id": "id_password1",
            }
        ),
    )
    password2 = forms.CharField(
        label="Confirm Password",
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "Confirm password",
                "id": "id_password2",
            }
        ),
    )
    first_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter your first name",
                "id": "id_first_name",
            }
        ),
    )
    last_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter your last name",
                "id": "id_last_name",
            }
        ),
    )
    travel_radius = forms.DecimalField(
        required=False,
        min_value=0,
        max_value=50,
        initial=0.0,
        validators=[MinValueValidator(0), MaxValueValidator(50)],
        help_text="Maximum travel distance in miles (0-50)",
        widget=forms.NumberInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter travel radius (in miles)",
                "id": "id_travel_radius",
                "min": "0",
                "max": "50",
                "step": "0.1",
            }
        ),
    )

    # Address fields
    address_line1 = forms.CharField(
        max_length=255,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control address-autocomplete",
                "placeholder": "Enter address line 1",
                "autocomplete": "address-line1",
                "id": "id_address_line1",
            }
        ),
    )
    address_line2 = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter address line 2",
                "autocomplete": "address-line2",
                "id": "id_address_line2",
            }
        ),
    )
    city = forms.CharField(
        max_length=100,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter city",
                "autocomplete": "address-level2",
                "id": "id_city",
            }
        ),
    )
    county = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter county",
                "autocomplete": "administrative-area",
                "id": "id_county",
            }
        ),
    )
    country = forms.CharField(
        max_length=100,
        required=True,
        initial="UK",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter country",
                "readonly": "readonly",
                "autocomplete": "country-name",
                "id": "id_country",
            }
        ),
    )
    postcode = forms.CharField(
        max_length=20,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter postcode",
                "autocomplete": "postal-code",
                "id": "id_postcode",
            }
        ),
    )
    latitude = forms.FloatField(
        required=False,
        widget=forms.HiddenInput(attrs={"id": "id_latitude"}),
    )
    longitude = forms.FloatField(
        required=False,
        widget=forms.HiddenInput(attrs={"id": "id_longitude"}),
    )

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2", "first_name", "last_name")
        widgets = {}

    def __init__(self, *args, **kwargs):
        self.invitation = kwargs.pop("invitation", None)
        self.request = kwargs.pop("request", None)
        super(AcceptInvitationForm, self).__init__(*args, **kwargs)
        if self.invitation:
            self.fields["email"].initial = self.invitation.email
        self.helper = FormHelper()
        self.helper.form_method = "post"
        self.helper.layout = Layout(
            "email",
            "username",
            Row(
                Column("first_name", css_class="form-group col-md-6 mb-0"),
                Column("last_name", css_class="form-group col-md-6 mb-0"),
            ),
            Row(
                Column("password1", css_class="form-group col-md-6 mb-0"),
                Column("password2", css_class="form-group col-md-6 mb-0"),
            ),
            "travel_radius",
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
        )

    def clean_email(self):
        """
        Ensures the email matches the invitation email and hasn't been used already.
        """
        email = self.cleaned_data.get("email", "").strip().lower()
        
        # Check that email matches the invitation
        if self.invitation and email != self.invitation.email:
            raise ValidationError("Email does not match the invitation email.")
            
        # Check that the invitation hasn't expired
        if self.invitation and self.invitation.is_expired():
            self.invitation.is_active = False
            self.invitation.save()
            raise ValidationError("This invitation has expired. Please request a new invitation.")
            
        # Check that the email isn't already in use by another user
        if User.objects.filter(email=email).exists():
            raise ValidationError("A user with this email already exists.")
            
        return email

    def clean_travel_radius(self):
        """
        Ensures that travel_radius is a valid decimal between 0 and 50.
        """
        travel_radius = self.cleaned_data.get("travel_radius")
        if travel_radius is None:
            return Decimal('0.0')
            
        try:
            travel_radius = Decimal(str(travel_radius))
            if travel_radius < 0 or travel_radius > 50:
                raise ValidationError("Travel radius must be between 0 and 50 miles.")
        except (InvalidOperation, TypeError, ValueError):
            raise ValidationError("Travel radius must be a valid number.")
            
        return travel_radius

    def clean(self):
        """
        Validates the form as a whole, including address geocoding.
        """
        cleaned_data = super().clean()
        
        # Check that the invitation exists and is active
        if not self.invitation or not self.invitation.is_active:
            self.add_error(None, "Invalid or inactive invitation.")
            return cleaned_data
            
        # Validate address fields
        address_line1 = cleaned_data.get("address_line1")
        city = cleaned_data.get("city")
        postcode = cleaned_data.get("postcode")
        
        if not address_line1 or not city or not postcode:
            if not address_line1:
                self.add_error("address_line1", "Address line 1 is required.")
            if not city:
                self.add_error("city", "City is required.")
            if not postcode:
                self.add_error("postcode", "Postcode is required.")
            return cleaned_data
            
        # Attempt to geocode the address
        address_components = [
            address_line1,
            cleaned_data.get("address_line2"),
            city,
            cleaned_data.get("county"),
            postcode,
            cleaned_data.get("country"),
        ]
        full_address = ", ".join(filter(None, address_components))

        try:
            geocode_result = geocode_address(full_address)
            if geocode_result:
                cleaned_data["latitude"] = geocode_result["latitude"]
                cleaned_data["longitude"] = geocode_result["longitude"]
                logger.info(f"Geocoded address for invitation acceptance: {full_address}")
            else:
                logger.warning(f"No geocoding results for address: {full_address}")
                self.add_error(None, "We couldn't find the location for this address. Please check and try again.")
        except Exception as e:
            logger.error(f"Failed to geocode address for invitation acceptance: {e}")
            # Don't block form submission due to geocoding failure
            self.add_error(None, "Could not validate address location. You may continue without geolocation or try a different address.")
            
        return cleaned_data

    def save(self, commit=True):
        """
        Saves the user, assigns to 'Agency Staff' group, and creates an associated Profile.
        """
        user = super().save(commit=False)
        user.email = self.cleaned_data.get("email", "").strip().lower()
        user.role = "staff"
        user.first_name = self.cleaned_data.get("first_name", "")
        user.last_name = self.cleaned_data.get("last_name", "")

        if commit:
            user.save()
            # Assign to 'Agency Staff' group
            assign_user_to_group(user, "Agency Staff")

            # Link the user to the agency associated with the invitation
            if self.invitation and self.invitation.agency:
                profile, created = Profile.objects.get_or_create(user=user)
                profile.agency = self.invitation.agency
                profile.travel_radius = self.cleaned_data.get("travel_radius") or 0.0
                profile.address_line1 = self.cleaned_data.get("address_line1")
                profile.address_line2 = self.cleaned_data.get("address_line2")
                profile.city = self.cleaned_data.get("city")
                profile.county = self.cleaned_data.get("county")
                profile.country = self.cleaned_data.get("country") or "UK"
                profile.postcode = self.cleaned_data.get("postcode")
                profile.latitude = self.cleaned_data.get("latitude")
                profile.longitude = self.cleaned_data.get("longitude")
                profile.save()
            else:
                profile, created = Profile.objects.get_or_create(user=user)
                profile.travel_radius = self.cleaned_data.get("travel_radius") or 0.0
                profile.address_line1 = self.cleaned_data.get("address_line1")
                profile.address_line2 = self.cleaned_data.get("address_line2")
                profile.city = self.cleaned_data.get("city")
                profile.county = self.cleaned_data.get("county")
                profile.country = self.cleaned_data.get("country") or "UK"
                profile.postcode = self.cleaned_data.get("postcode")
                profile.latitude = self.cleaned_data.get("latitude")
                profile.longitude = self.cleaned_data.get("longitude")
                profile.save()

            # Mark the invitation as used
            if self.invitation:
                self.invitation.is_active = False
                self.invitation.accepted_at = timezone.now()
                self.invitation.save()

            # Log the acceptance of the invitation
            logger.info(f"Invitation accepted by user: {user.username}")

            # Log the user in
            if self.request:
                login(self.request, user)

        return user


class ProfilePictureForm(forms.ModelForm):
    """
    Form for uploading and updating the profile picture.
    """

    class Meta:
        model = Profile
        fields = ["profile_picture"]
        widgets = {
            "profile_picture": forms.ClearableFileInput(
                attrs={
                    "class": "form-control-file",
                    "id": "id_profile_picture",
                }
            ),
        }

    def clean_profile_picture(self):
        """
        Validates the uploaded profile picture for size, format, and dimensions.
        """
        picture = self.cleaned_data.get("profile_picture", None)
        if not picture:
            return picture
            
        # Validate file size (max 5MB)
        max_file_size = 5 * 1024 * 1024
        if picture.size > max_file_size:
            logger.warning(f"Profile picture too large: {picture.size} bytes")
            raise ValidationError("Image file is too large. Maximum size is 5MB.")
            
        # Validate image format
        try:
            img = Image.open(picture)
            if img.format.lower() not in ["jpeg", "jpg", "png", "gif"]:
                logger.warning(f"Unsupported image format: {img.format}")
                raise ValidationError("Unsupported image format. Please use JPEG, PNG, or GIF.")
                
            # Validate dimensions
            width, height = img.size
            if width > 2000 or height > 2000:
                logger.warning(f"Image dimensions too large: {width}x{height}")
                raise ValidationError("Image dimensions are too large. Maximum dimensions are 2000x2000 pixels.")
                
        except (IOError, SyntaxError) as e:
            logger.error(f"Invalid image file: {e}")
            raise ValidationError("Invalid image file. Please upload a valid image.")
            
        return picture


class UpdateProfileForm(AddressFormMixin, forms.ModelForm):
    """
    Form for users to update their profile information (excluding profile picture).
    """

    class Meta:
        model = Profile
        fields = [
            "address_line1",
            "address_line2",
            "city",
            "county",
            "country",
            "postcode",
            "travel_radius",
            "latitude",
            "longitude",
        ]
        widgets = {
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
            "travel_radius": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": "0",
                    "max": "50",
                    "step": "0.1",
                    "placeholder": "Travel Radius (miles)",
                    "id": "id_travel_radius",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super(UpdateProfileForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = "post"
        self.helper.layout = Layout(
            "address_line1",
            "address_line2",
            Row(
                Column("city", css_class="form-group col-md-4 mb-0"),
                Column("county", css_class="form-group col-md-4 mb-0"),
                Column("postcode", css_class="form-group col-md-4 mb-0"),
            ),
            Row(
                Column("country", css_class="form-group col-md-6 mb-0"),
                Column("travel_radius", css_class="form-group col-md-6 mb-0"),
            ),
            # Hidden fields
            Field("latitude"),
            Field("longitude"),
        )

    def clean_postcode(self):
        """
        Validates the postcode based on UK-specific formats.
        """
        postcode = self.cleaned_data.get("postcode", "").strip()
        if not postcode:
            return postcode
            
        # UK postcode regex
        uk_postcode_regex = r"^[A-Z]{1,2}\d[A-Z\d]? ?\d[A-Z]{2}$"
        if not re.match(uk_postcode_regex, postcode.upper()):
            raise ValidationError("Enter a valid UK postcode.")
            
        return postcode.upper()

    def clean_travel_radius(self):
        """
        Ensures that travel_radius is a valid decimal between 0 and 50.
        """
        travel_radius = self.cleaned_data.get("travel_radius")
        if travel_radius is None:
            return Decimal('0.0')
            
        try:
            travel_radius = Decimal(str(travel_radius))
            if travel_radius < 0 or travel_radius > 50:
                raise ValidationError("Travel radius must be between 0 and 50 miles.")
        except (InvalidOperation, TypeError, ValueError):
            raise ValidationError("Travel radius must be a valid number.")
            
        return travel_radius

    def clean(self):
        """
        Validates the form as a whole, including address geocoding.
        """
        cleaned_data = super().clean()
        
        # Validate address fields
        address_line1 = cleaned_data.get("address_line1")
        city = cleaned_data.get("city")
        postcode = cleaned_data.get("postcode")
        
        # Only attempt geocoding if sufficient address data is provided
        if address_line1 or (city and postcode):
            # Construct the full address for geocoding
            address_components = [
                address_line1,
                cleaned_data.get("address_line2"),
                city,
                cleaned_data.get("county"),
                postcode,
                cleaned_data.get("country"),
            ]
            full_address = ", ".join(filter(None, address_components))

            try:
                geocode_result = geocode_address(full_address)
                if geocode_result:
                    cleaned_data["latitude"] = geocode_result["latitude"]
                    cleaned_data["longitude"] = geocode_result["longitude"]
                    logger.info(f"Geocoded address for profile update: {full_address}")
                else:
                    logger.warning(f"No geocoding results for address: {full_address}")
                    self.add_error(None, "We couldn't find the location for this address. Please check and try again.")
            except Exception as e:
                logger.error(f"Failed to geocode address for profile update: {e}")
                # Don't block form submission due to geocoding failure
                self.add_error(None, "Could not validate address location. You may continue without geolocation or try a different address.")
            
        return cleaned_data

    def save(self, commit=True):
        """
        Override save method to update Profile.
        """
        profile = super().save(commit=False)
        if commit:
            profile.save()
        return profile


class UserForm(UserCreationForm):
    """
    Form for creating users via Class-Based Views.
    """

    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter email",
                "required": True,
                "id": "id_email",
            }
        ),
    )
    first_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter first name",
                "id": "id_first_name",
            }
        ),
    )
    last_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter last name",
                "id": "id_last_name",
            }
        ),
    )
    group = forms.ModelChoiceField(
        queryset=Group.objects.all(),
        required=True,
        widget=forms.Select(attrs={"class": "form-control", "id": "id_group"}),
        label="Group",
    )

    class Meta:
        model = User
        fields = (
            "username",
            "email",
            "first_name",
            "last_name",
            "password1",
            "password2",
            "group",
        )
        widgets = {
            "username": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Enter username",
                    "id": "id_username",
                }
            ),
            "password1": forms.PasswordInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Enter password",
                    "id": "id_password1",
                }
            ),
            "password2": forms.PasswordInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Confirm password",
                    "id": "id_password2",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super(UserForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = "post"
        self.helper.layout = Layout(
            Row(
                Column("username", css_class="form-group col-md-6 mb-0"),
                Column("email", css_class="form-group col-md-6 mb-0"),
            ),
            Row(
                Column("first_name", css_class="form-group col-md-6 mb-0"),
                Column("last_name", css_class="form-group col-md-6 mb-0"),
            ),
            "group",
            Row(
                Column("password1", css_class="form-group col-md-6 mb-0"),
                Column("password2", css_class="form-group col-md-6 mb-0"),
            ),
        )

    def clean_email(self):
        """
        Ensures the email is unique.
        """
        email = self.cleaned_data.get("email", "").strip().lower()
        if not email:
            raise ValidationError("Email is required.")
            
        try:
            forms.EmailField().clean(email)
        except ValidationError:
            raise ValidationError("Enter a valid email address.")
            
        if User.objects.filter(email=email).exists():
            raise ValidationError("A user with this email already exists.")
            
        return email


class UserUpdateForm(UserChangeForm):
    """
    Form for updating users via Class-Based Views without changing the password.
    """

    password = None  # Exclude the password field

    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter email",
                "required": True,
                "id": "id_email",
            }
        ),
    )
    first_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter first name",
                "id": "id_first_name",
            }
        ),
    )
    last_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter last name",
                "id": "id_last_name",
            }
        ),
    )
    group = forms.ModelChoiceField(
        queryset=Group.objects.all(),
        required=True,
        widget=forms.Select(attrs={"class": "form-control", "id": "id_group"}),
        label="Group",
    )
    is_active = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(
            attrs={
                "class": "form-check-input",
                "id": "id_is_active",
            }
        ),
        label="Is Active",
    )

    class Meta:
        model = User
        fields = ("username", "email", "first_name", "last_name", "group", "is_active")
        widgets = {
            "username": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Enter username",
                    "id": "id_username",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super(UserUpdateForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = "post"
        self.helper.layout = Layout(
            Row(
                Column("email", css_class="form-group col-md-6 mb-0"),
                Column("is_active", css_class="form-group col-md-6 mb-0"),
            ),
            Row(
                Column("first_name", css_class="form-group col-md-6 mb-0"),
                Column("last_name", css_class="form-group col-md-6 mb-0"),
            ),
            "group",
            "username",
        )
        
        # Initialize with current group if already set
        if self.instance and self.instance.pk:
            group = self.instance.groups.first()
            if group:
                self.initial["group"] = group.pk

    def clean_email(self):
        """
        Ensures the email remains unique.
        """
        email = self.cleaned_data.get("email", "").strip().lower()
        if not email:
            raise ValidationError("Email is required.")
            
        try:
            forms.EmailField().clean(email)
        except ValidationError:
            raise ValidationError("Enter a valid email address.")
            
        existing_user = User.objects.filter(email=email).exclude(pk=self.instance.pk).first()
        if existing_user:
            raise ValidationError("This email is already in use by another user.")
            
        return email

    def save(self, commit=True):
        """
        Save the form and update group membership.
        """
        user = super().save(commit=False)
        
        if commit:
            user.save()
            
            # Update group membership
            group = self.cleaned_data.get("group")
            if group:
                # Clear existing groups and add the selected one
                user.groups.clear()
                user.groups.add(group)
                
        return user


class StaffCreationForm(AddressFormMixin, UserCreationForm):
    """
    Form for agency managers to add new staff members.
    """

    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter staff email",
                "required": True,
                "id": "id_email",
            }
        ),
    )
    first_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter staff first name",
                "id": "id_first_name",
            }
        ),
    )
    last_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter staff last name",
                "id": "id_last_name",
            }
        ),
    )
    travel_radius = forms.DecimalField(
        required=False,
        min_value=0,
        max_value=50,
        initial=0.0,
        validators=[MinValueValidator(0), MaxValueValidator(50)],
        help_text="Maximum travel distance in miles (0-50)",
        widget=forms.NumberInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter travel radius (in miles)",
                "id": "id_travel_radius",
                "min": "0",
                "max": "50",
                "step": "0.1",
            }
        ),
    )

    # Address fields
    address_line1 = forms.CharField(
        max_length=255,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control address-autocomplete",
                "placeholder": "Enter address line 1",
                "autocomplete": "address-line1",
                "id": "id_address_line1",
            }
        ),
    )
    address_line2 = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter address line 2",
                "autocomplete": "address-line2",
                "id": "id_address_line2",
            }
        ),
    )
    city = forms.CharField(
        max_length=100,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter city",
                "autocomplete": "address-level2",
                "id": "id_city",
            }
        ),
    )
    county = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter county",
                "autocomplete": "administrative-area",
                "id": "id_county",
            }
        ),
    )
    country = forms.CharField(
        max_length=100,
        required=True,
        initial="UK",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter country",
                "readonly": "readonly",
                "autocomplete": "country-name",
                "id": "id_country",
            }
        ),
    )
    postcode = forms.CharField(
        max_length=20,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter postcode",
                "autocomplete": "postal-code",
                "id": "id_postcode",
            }
        ),
    )
    latitude = forms.FloatField(
        required=False,
        widget=forms.HiddenInput(attrs={"id": "id_latitude"}),
    )
    longitude = forms.FloatField(
        required=False,
        widget=forms.HiddenInput(attrs={"id": "id_longitude"}),
    )

    class Meta:
        model = User
        fields = (
            "username",
            "email",
            "password1",
            "password2",
            "first_name",
            "last_name",
        )
        widgets = {
            "username": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Enter username",
                    "id": "id_username",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        super(StaffCreationForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = "post"
        self.helper.layout = Layout(
            Row(
                Column("username", css_class="form-group col-md-6 mb-0"),
                Column("email", css_class="form-group col-md-6 mb-0"),
            ),
            Row(
                Column("password1", css_class="form-group col-md-6 mb-0"),
                Column("password2", css_class="form-group col-md-6 mb-0"),
            ),
            Row(
                Column("first_name", css_class="form-group col-md-6 mb-0"),
                Column("last_name", css_class="form-group col-md-6 mb-0"),
            ),
            "travel_radius",
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
        )
        
        # Add agency field for superusers
        if self.request and self.request.user.is_superuser:
            self.fields["agency"] = forms.ModelChoiceField(
                queryset=Agency.objects.all(),
                required=True,
                widget=forms.Select(attrs={"class": "form-control", "id": "id_agency"}),
                help_text="Select an agency for this staff member.",
            )
            self.helper.layout.insert(3, "agency")

    def clean_email(self):
        """
        Validates the email is unique and not already in use.
        """
        email = self.cleaned_data.get("email", "").strip().lower()
        if not email:
            raise ValidationError("Email is required.")
            
        try:
            forms.EmailField().clean(email)
        except ValidationError:
            raise ValidationError("Enter a valid email address.")
            
        if User.objects.filter(email=email).exists():
            raise ValidationError("A user with this email already exists.")
            
        return email

    def clean_travel_radius(self):
        """
        Ensures that travel_radius is a valid decimal between 0 and 50.
        """
        travel_radius = self.cleaned_data.get("travel_radius")
        if travel_radius is None:
            return Decimal('0.0')
            
        try:
            travel_radius = Decimal(str(travel_radius))
            if travel_radius < 0 or travel_radius > 50:
                raise ValidationError("Travel radius must be between 0 and 50 miles.")
        except (InvalidOperation, TypeError, ValueError):
            raise ValidationError("Travel radius must be a valid number.")
            
        return travel_radius

    def clean(self):
        """
        Validates the form as a whole, including address geocoding.
        """
        cleaned_data = super().clean()
        
        # Validate address fields
        address_line1 = cleaned_data.get("address_line1")
        city = cleaned_data.get("city")
        postcode = cleaned_data.get("postcode")
        
        if not address_line1 or not city or not postcode:
            if not address_line1:
                self.add_error("address_line1", "Address line 1 is required.")
            if not city:
                self.add_error("city", "City is required.")
            if not postcode:
                self.add_error("postcode", "Postcode is required.")
            return cleaned_data
            
        # Attempt to geocode the address
        address_components = [
            address_line1,
            cleaned_data.get("address_line2"),
            city,
            cleaned_data.get("county"),
            postcode,
            cleaned_data.get("country"),
        ]
        full_address = ", ".join(filter(None, address_components))

        try:
            geocode_result = geocode_address(full_address)
            if geocode_result:
                cleaned_data["latitude"] = geocode_result["latitude"]
                cleaned_data["longitude"] = geocode_result["longitude"]
                logger.info(f"Geocoded address for staff creation: {full_address}")
            else:
                logger.warning(f"No geocoding results for address: {full_address}")
                self.add_error(None, "We couldn't find the location for this address. Please check and try again.")
        except Exception as e:
            logger.error(f"Failed to geocode address for staff creation: {e}")
            # Don't block form submission due to geocoding failure
            self.add_error(None, "Could not validate address location. You may continue without geolocation or try a different address.")
            
        return cleaned_data

    def save(self, commit=True):
        """
        Saves the user and associates them with the 'Agency Staff' group and their agency.
        """
        user = super().save(commit=False)
        user.email = self.cleaned_data.get("email", "").strip().lower()
        user.role = "staff"
        user.first_name = self.cleaned_data.get("first_name", "")
        user.last_name = self.cleaned_data.get("last_name", "")

        if commit:
            user.save()
            # Assign user to 'Agency Staff' group
            assign_user_to_group(user, "Agency Staff")

            # Set agency based on superuser selection or requester's agency
            profile, created = Profile.objects.get_or_create(user=user)
            
            # Determine agency
            agency = None
            if self.request and self.request.user.is_superuser:
                agency = self.cleaned_data.get("agency")
            elif self.request and hasattr(self.request.user, "profile") and self.request.user.profile.agency:
                agency = self.request.user.profile.agency
                
            if not agency:
                raise ValidationError("No agency could be determined for this staff member.")
                
            # Update profile
            profile.agency = agency
            profile.travel_radius = self.cleaned_data.get("travel_radius") or 0.0
            profile.address_line1 = self.cleaned_data.get("address_line1")
            profile.address_line2 = self.cleaned_data.get("address_line2")
            profile.city = self.cleaned_data.get("city")
            profile.county = self.cleaned_data.get("county")
            profile.country = self.cleaned_data.get("country") or "UK"
            profile.postcode = self.cleaned_data.get("postcode")
            profile.latitude = self.cleaned_data.get("latitude")
            profile.longitude = self.cleaned_data.get("longitude")
            profile.save()

            # Log the creation of a new user
            logger.info(f"New staff member created: {user.username} for agency {agency.name}")

        return user


class StaffUpdateForm(AddressFormMixin, forms.ModelForm):
    """
    Form for agency managers to update existing staff members.
    """

    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter email",
                "required": True,
                "id": "id_email",
            }
        ),
    )
    first_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter first name",
                "id": "id_first_name",
            }
        ),
    )
    last_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter last name",
                "id": "id_last_name",
            }
        ),
    )
    is_active = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(
            attrs={
                "class": "form-check-input",
                "id": "id_is_active",
            }
        ),
        label="Is Active",
    )
    travel_radius = forms.DecimalField(
        required=False,
        min_value=0,
        max_value=50,
        initial=0.0,
        validators=[MinValueValidator(0), MaxValueValidator(50)],
        help_text="Maximum travel distance in miles (0-50)",
        widget=forms.NumberInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter travel radius (in miles)",
                "id": "id_travel_radius",
                "min": "0",
                "max": "50",
                "step": "0.1",
            }
        ),
    )

    # Address fields - same as in StaffCreationForm
    address_line1 = forms.CharField(
        max_length=255,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control address-autocomplete",
                "placeholder": "Enter address line 1",
                "autocomplete": "address-line1",
                "id": "id_address_line1",
            }
        ),
    )
    address_line2 = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter address line 2",
                "autocomplete": "address-line2",
                "id": "id_address_line2",
            }
        ),
    )
    city = forms.CharField(
        max_length=100,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter city",
                "autocomplete": "address-level2",
                "id": "id_city",
            }
        ),
    )
    county = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter county",
                "autocomplete": "administrative-area",
                "id": "id_county",
            }
        ),
    )
    country = forms.CharField(
        max_length=100,
        required=True,
        initial="UK",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter country",
                "readonly": "readonly",
                "autocomplete": "country-name",
                "id": "id_country",
            }
        ),
    )
    postcode = forms.CharField(
        max_length=20,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter postcode",
                "autocomplete": "postal-code",
                "id": "id_postcode",
            }
        ),
    )
    latitude = forms.FloatField(
        required=False,
        widget=forms.HiddenInput(attrs={"id": "id_latitude"}),
    )
    longitude = forms.FloatField(
        required=False,
        widget=forms.HiddenInput(attrs={"id": "id_longitude"}),
    )

    class Meta:
        model = User
        fields = ("email", "first_name", "last_name", "is_active")
        widgets = {}

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        super(StaffUpdateForm, self).__init__(*args, **kwargs)
        
        # Initialize layout
        self.helper = FormHelper()
        self.helper.form_method = "post"
        self.helper.layout = Layout(
            Row(
                Column("email", css_class="form-group col-md-6 mb-0"),
                Column("is_active", css_class="form-group col-md-6 mb-0"),
            ),
            Row(
                Column("first_name", css_class="form-group col-md-6 mb-0"),
                Column("last_name", css_class="form-group col-md-6 mb-0"),
            ),
            "travel_radius",
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
        )
        
        # Add agency field for superusers
        if self.request and self.request.user.is_superuser:
            self.fields["agency"] = forms.ModelChoiceField(
                queryset=Agency.objects.all(),
                required=True,
                widget=forms.Select(attrs={"class": "form-control", "id": "id_agency"}),
                help_text="Select an agency for this staff member.",
            )
            self.helper.layout.insert(3, "agency")
            
            # Set initial agency value if profile exists
            if self.instance and hasattr(self.instance, "profile") and self.instance.profile.agency:
                self.fields["agency"].initial = self.instance.profile.agency
        
        # Initialize address fields from profile if they exist
        if self.instance and hasattr(self.instance, "profile"):
            profile = self.instance.profile
            self.fields["travel_radius"].initial = profile.travel_radius
            self.fields["address_line1"].initial = profile.address_line1
            self.fields["address_line2"].initial = profile.address_line2
            self.fields["city"].initial = profile.city
            self.fields["county"].initial = profile.county
            self.fields["country"].initial = profile.country
            self.fields["postcode"].initial = profile.postcode
            self.fields["latitude"].initial = profile.latitude
            self.fields["longitude"].initial = profile.longitude

    def clean_email(self):
        """
        Ensures the email remains unique.
        """
        email = self.cleaned_data.get("email", "").strip().lower()
        if not email:
            raise ValidationError("Email is required.")
            
        try:
            forms.EmailField().clean(email)
        except ValidationError:
            raise ValidationError("Enter a valid email address.")
            
        # Check that email is unique, excluding current instance
        if User.objects.filter(email=email).exclude(pk=self.instance.pk).exists():
            raise ValidationError("This email is already in use by another user.")
            
        return email

    def clean_travel_radius(self):
        """
        Ensures that travel_radius is a valid decimal between 0 and 50.
        """
        travel_radius = self.cleaned_data.get("travel_radius")
        if travel_radius is None:
            return Decimal('0.0')
            
        try:
            travel_radius = Decimal(str(travel_radius))
            if travel_radius < 0 or travel_radius > 50:
                raise ValidationError("Travel radius must be between 0 and 50 miles.")
        except (InvalidOperation, TypeError, ValueError):
            raise ValidationError("Travel radius must be a valid number.")
            
        return travel_radius

    def clean(self):
        """
        Validates the form as a whole, including address geocoding.
        """
        cleaned_data = super().clean()
        
        # Validate address fields
        address_line1 = cleaned_data.get("address_line1")
        city = cleaned_data.get("city")
        postcode = cleaned_data.get("postcode")
        
        if not address_line1 or not city or not postcode:
            if not address_line1:
                self.add_error("address_line1", "Address line 1 is required.")
            if not city:
                self.add_error("city", "City is required.")
            if not postcode:
                self.add_error("postcode", "Postcode is required.")
            return cleaned_data
            
        # Attempt to geocode the address
        address_components = [
            address_line1,
            cleaned_data.get("address_line2"),
            city,
            cleaned_data.get("county"),
            postcode,
            cleaned_data.get("country"),
        ]
        full_address = ", ".join(filter(None, address_components))

        try:
            geocode_result = geocode_address(full_address)
            if geocode_result:
                cleaned_data["latitude"] = geocode_result["latitude"]
                cleaned_data["longitude"] = geocode_result["longitude"]
                logger.info(f"Geocoded address for staff update: {full_address}")
            else:
                logger.warning(f"No geocoding results for address: {full_address}")
                self.add_error(None, "We couldn't find the location for this address. Please check and try again.")
        except Exception as e:
            logger.error(f"Failed to geocode address for staff update: {e}")
            # Don't block form submission due to geocoding failure
            self.add_error(None, "Could not validate address location. You may continue without geolocation or try a different address.")
            
        return cleaned_data

    def save(self, commit=True):
        """
        Saves the user and updates the associated Profile.
        """
        user = super().save(commit=False)
        user.email = self.cleaned_data.get("email", "").strip().lower()
        user.first_name = self.cleaned_data.get("first_name", "")
        user.last_name = self.cleaned_data.get("last_name", "")

        if commit:
            user.save()
            
            # Update profile
            profile, created = Profile.objects.get_or_create(user=user)
            
            # Set agency if provided (for superusers)
            if self.request and self.request.user.is_superuser and "agency" in self.cleaned_data:
                profile.agency = self.cleaned_data["agency"]
            
            # Update other profile fields
            profile.travel_radius = self.cleaned_data.get("travel_radius") or 0.0
            profile.address_line1 = self.cleaned_data.get("address_line1")
            profile.address_line2 = self.cleaned_data.get("address_line2")
            profile.city = self.cleaned_data.get("city")
            profile.county = self.cleaned_data.get("county")
            profile.country = self.cleaned_data.get("country") or "UK"
            profile.postcode = self.cleaned_data.get("postcode")
            profile.latitude = self.cleaned_data.get("latitude")
            profile.longitude = self.cleaned_data.get("longitude")
            profile.save()

            # Log the update
            logger.info(f"Staff member updated: {user.username}")

        return user


class ActivateTOTPForm(forms.Form):
    """
    Form for enabling Two-Factor Authentication using TOTP.
    """
    totp_code = forms.CharField(
        max_length=6,
        min_length=6,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter code from authenticator",
                "id": "id_totp_code",
                "inputmode": "numeric",
                "pattern": "[0-9]*",
            }
        ),
        label="Enter TOTP Code",
        help_text="Enter the 6-digit code from your authenticator app."
    )

    def clean_totp_code(self):
        """Validates that the TOTP code consists only of digits."""
        code = self.cleaned_data.get("totp_code", "").strip()
        if not code:
            raise ValidationError("TOTP code is required.")
            
        if not code.isdigit():
            raise ValidationError("TOTP code must contain only digits.")
            
        if len(code) != 6:
            raise ValidationError("TOTP code must be 6 digits long.")
            
        return code


class RecoveryCodeForm(forms.Form):
    """
    Form for using recovery codes to log in when MFA is enabled.
    """
    recovery_code = forms.CharField(
        max_length=8,
        min_length=8,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Recovery Code",
                "id": "id_recovery_code",
                "autocomplete": "off",
            }
        ),
        label="Recovery Code",
        help_text="Enter one of your recovery codes to regain access to your account."
    )

    def clean_recovery_code(self):
        """Validates the recovery code format."""
        code = self.cleaned_data.get("recovery_code", "").strip().upper()
        if not code:
            raise ValidationError("Recovery code is required.")
            
        if len(code) != 8:
            raise ValidationError("Recovery codes are 8 characters long.")
            
        # Recovery codes should be alphanumeric
        if not code.isalnum():
            raise ValidationError("Recovery code should only contain letters and numbers.")
            
        return code


class MFAForm(forms.Form):
    """
    Form for MFA verification during login.
    """
    totp_code = forms.CharField(
        max_length=6,
        min_length=6,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter MFA code",
                "id": "id_totp_code",
                "inputmode": "numeric",
                "pattern": "[0-9]*",
                "autocomplete": "one-time-code",
            }
        ),
        label="MFA Code",
        help_text="Enter the 6-digit code from your authenticator app."
    )

    def clean_totp_code(self):
        """Validates that the TOTP code consists only of digits."""
        code = self.cleaned_data.get("totp_code", "").strip()
        if not code:
            raise ValidationError("MFA code is required.")
            
        if not code.isdigit():
            raise ValidationError("MFA code must contain only digits.")
            
        if len(code) != 6:
            raise ValidationError("MFA code must be 6 digits long.")
            
        return code