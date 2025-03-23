# /workspace/shiftwise/accounts/forms.py

import logging
import re
import socket

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Column, Field, Layout, Row
from django import forms
from django.contrib.auth import get_user_model, login
from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.utils import timezone
from PIL import Image, ImageOps

from core.constants import AGENCY_TYPE_CHOICES, ROLE_CHOICES
from core.forms import AddressFormMixin
from core.utils import assign_user_to_group, generate_unique_code
from shiftwise.utils import geocode_address
from accounts.validators import validate_uk_phone_number

from .models import Agency, Invitation, Profile

User = get_user_model()

# Configure logging
logger = logging.getLogger(__name__)


class AgencyForm(AddressFormMixin, forms.ModelForm):
    """Form for creating and updating Agency records with geocoding support"""

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
                    "placeholder": "UK Phone Number (e.g., +44 1234 567890)",
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
                    "autocomplete": "address-level1",
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
            "country",
            "email",
            "phone_number",
            "website",
            # Hidden fields
            Field("latitude"),
            Field("longitude"),
        )

    def clean_email(self):
        """Validates email uniqueness and format"""
        email = (self.cleaned_data.get("email") or "").strip().lower()
        if not email:
            raise ValidationError("Email is required.")
        
        try:
            forms.EmailField().clean(email)
        except ValidationError:
            raise ValidationError("Enter a valid email address.")
            
        if Agency.objects.filter(email=email).exclude(pk=self.instance.pk).exists():
            raise ValidationError("An agency with this email already exists.")
        return email
    
    def clean_phone_number(self):
        """Applies UK phone number format validation"""
        phone_number = self.cleaned_data.get("phone_number")
        if phone_number:
            return validate_uk_phone_number(phone_number)
        return phone_number

    def clean(self):
        """Geocodes address and validates required fields"""
        cleaned_data = super().clean()
        address_line1 = cleaned_data.get("address_line1")
        address_line2 = cleaned_data.get("address_line2")
        city = cleaned_data.get("city")
        county = cleaned_data.get("county")
        postcode = cleaned_data.get("postcode")
        country = cleaned_data.get("country")

        # Verify required address fields
        if not address_line1:
            self.add_error("address_line1", "Address line 1 is required.")
        if not city:
            self.add_error("city", "City is required.")
        if not postcode:
            self.add_error("postcode", "Postcode is required.")

        # Construct the full address
        address_components = [
            address_line1,
            address_line2,
            city,
            county,
            postcode,
            country,
        ]
        full_address = ", ".join(filter(None, address_components))

        if full_address.strip():
            try:
                geocode_result = geocode_address(full_address)
                cleaned_data["latitude"] = geocode_result["latitude"]
                cleaned_data["longitude"] = geocode_result["longitude"]
                logger.info(f"Geocoded address for agency: {full_address}")
            except Exception as e:
                logger.error(f"Failed to geocode address for agency: {e}")
                # Don't block submission, just add a warning
                self.add_error(None, "Unable to geocode address. Location-based features may not work correctly.")
        
        return cleaned_data

    def clean_postcode(self):
        """Validates UK postcode format"""
        postcode = self.cleaned_data.get("postcode")
        if postcode:
            postcode = postcode.strip()
        else:
            postcode = ""

        if not postcode:
            # If no postcode is provided, return it as is
            return postcode

        # UK postcode regex
        uk_postcode_regex = r"^[A-Z]{1,2}\d[A-Z\d]? ?\d[A-Z]{2}$"
        if not re.match(uk_postcode_regex, postcode.upper()):
            raise ValidationError("Enter a valid UK postcode.")
        return postcode.upper()

    def clean_latitude(self):
        """Validates latitude range (-90 to 90)"""
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
        """Validates longitude range (-180 to 180)"""
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
        """Generates agency code if needed and saves the instance"""
        agency = super().save(commit=False)

        if not agency.agency_code:
            agency.agency_code = generate_unique_code(prefix="AG-", length=8)

        agency.clean()

        if commit:
            agency.save()
            self.save_m2m()
        return agency


class AgencySignUpForm(AddressFormMixin, UserCreationForm):
    """Combined form for creating agency owner account and agency profile"""

    # Agency-specific fields
    agency_name = forms.CharField(
        max_length=100,
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
                "autocomplete": "address-level1",
                "id": "id_county",
            }
        ),
    )
    country = forms.CharField(
        max_length=100,
        required=False,
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
            Row(
                Column("agency_email", css_class="form-group col-md-6 mb-0"),
                Column("agency_phone_number", css_class="form-group col-md-6 mb-0"),
            ),
            "agency_website",
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
        
        # Make first_name and last_name required
        self.fields['first_name'].required = True
        self.fields['last_name'].required = True

    def clean_email(self):
        """Validates email uniqueness and DNS record existence"""
        email = self.cleaned_data.get("email", "").strip().lower()
        if not email:
            raise ValidationError("Email is required.")
        
        try:
            forms.EmailField().clean(email)
        except ValidationError:
            raise ValidationError("Enter a valid email address.")
            
        if User.objects.filter(email=email).exists():
            raise ValidationError("A user with this email already exists.")
        
        domain = email.split('@')[-1]
        try:
            socket.gethostbyname(domain)
        except socket.gaierror:
            self.add_error(None, f"Warning: The domain '{domain}' might not exist. Please double-check your email.")
            
        return email
    
    def clean_agency_email(self):
        """Validates agency email format"""
        email = self.cleaned_data.get("agency_email", "").strip().lower()
        if not email:
            raise ValidationError("Agency email is required.")
        
        try:
            forms.EmailField().clean(email)
        except ValidationError:
            raise ValidationError("Enter a valid email address.")
            
        return email
        
    def clean_agency_phone_number(self):
        """Validates UK phone number format"""
        phone = self.cleaned_data.get("agency_phone_number", "").strip()
        if not phone:
            return phone
            
        uk_phone_regex = r"^(\+44|0)( |-|\()?(\d{1,5})( |-|\))?(\d{3,10})$"
        if not re.match(uk_phone_regex, phone):
            raise ValidationError("Enter a valid UK phone number.")
            
        return phone

    def clean_postcode(self):
        """Validates UK postcode format"""
        postcode = self.cleaned_data.get("postcode")
        if postcode:
            postcode = postcode.strip()
        else:
            postcode = ""

        if not postcode:
            raise ValidationError("Postcode is required.")

        uk_postcode_regex = r"^[A-Z]{1,2}\d[A-Z\d]? ?\d[A-Z]{2}$"
        if not re.match(uk_postcode_regex, postcode.upper()):
            raise ValidationError("Enter a valid UK postcode.")
        return postcode.upper()

    def clean(self):
        """Cross-validates fields and geocodes address"""
        cleaned_data = super().clean()
        address_line1 = cleaned_data.get("address_line1")
        address_line2 = cleaned_data.get("address_line2")
        city = cleaned_data.get("city")
        county = cleaned_data.get("county")
        postcode = cleaned_data.get("postcode")
        country = cleaned_data.get("country")

        if not address_line1:
            self.add_error("address_line1", "Address line 1 is required.")
        if not city:
            self.add_error("city", "City is required.")
        if not postcode:
            self.add_error("postcode", "Postcode is required.")

        user_email = cleaned_data.get("email", "").strip().lower()
        agency_email = cleaned_data.get("agency_email", "").strip().lower()
        
        if user_email and agency_email and user_email != agency_email:
            self.add_error(None, "Note: Your personal email and agency email are different. Agency email will be used for business communications.")

        address_components = [
            address_line1,
            address_line2,
            city,
            county,
            postcode,
            country or "UK",
        ]
        full_address = ", ".join(filter(None, address_components))

        if full_address.strip():
            try:
                geocode_result = geocode_address(full_address)
                cleaned_data["latitude"] = geocode_result["latitude"]
                cleaned_data["longitude"] = geocode_result["longitude"]
                logger.info(f"Geocoded address for agency signup: {full_address}")
            except Exception as e:
                logger.error(f"Failed to geocode address for agency signup: {e}")
                self.add_error(None, "Unable to geocode address. Location-based features may not work correctly.")
        
        return cleaned_data

    def save(self, commit=True):
        """Creates user account, agency record, and links them together"""
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"].strip().lower()
        user.role = "agency_owner"

        if commit:
            user.save()
            assign_user_to_group(user, "Agency Owners")

            try:
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
                profile.travel_radius = 0.0
                profile.save()
                
                logger.info(f"New agency owner created: {user.username}, Agency: {agency.name}")
            except Exception as e:
                logger.error(f"Error creating agency for user {user.username}: {e}")
                user.delete()
                raise ValidationError(f"Agency creation failed: {str(e)}")

        return user


class SignUpForm(AddressFormMixin, UserCreationForm):
    """Registration form for new staff members"""

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
        widget=forms.NumberInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter travel radius (in miles)",
                "id": "id_travel_radius",
            }
        ),
        help_text="Maximum distance you're willing to travel for shifts (in miles)."
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
                "autocomplete": "address-level1",
                "id": "id_county",
            }
        ),
    )
    country = forms.CharField(
        max_length=100,
        required=False,
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
        # Request param allows access to the inviting user
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
        """Validates email uniqueness and DNS record existence"""
        email = self.cleaned_data.get("email", "").strip().lower()
        if not email:
            raise ValidationError("Email is required.")
        try:
            forms.EmailField().clean(email)
        except ValidationError:
            raise ValidationError("Enter a valid email address.")
        if User.objects.filter(email=email).exists():
            raise ValidationError("A user with this email already exists.")
            
        domain = email.split('@')[-1]
        try:
            socket.gethostbyname(domain)
        except socket.gaierror:
            self.add_error(None, f"Warning: The domain '{domain}' might not exist. Please double-check your email.")
            
        return email

    def clean_travel_radius(self):
        """Validates travel radius limits (0-50 miles)"""
        travel_radius = self.cleaned_data.get("travel_radius")
        if travel_radius is None:
            return 0.0
        if travel_radius < 0 or travel_radius > 50:
            raise ValidationError("Travel radius must be between 0 and 50 miles.")
        return travel_radius

    def clean_postcode(self):
        """Validates UK postcode format"""
        postcode = self.cleaned_data.get("postcode")
        if postcode:
            postcode = postcode.strip()
        else:
            raise ValidationError("Postcode is required.")

        uk_postcode_regex = r"^[A-Z]{1,2}\d[A-Z\d]? ?\d[A-Z]{2}$"
        if not re.match(uk_postcode_regex, postcode.upper()):
            raise ValidationError("Enter a valid UK postcode.")
        return postcode.upper()

    def clean(self):
        """Validates password security and geocodes address"""
        cleaned_data = super().clean()
        address_line1 = cleaned_data.get("address_line1")
        address_line2 = cleaned_data.get("address_line2")
        city = cleaned_data.get("city")
        county = cleaned_data.get("county")
        postcode = cleaned_data.get("postcode")
        country = cleaned_data.get("country")
        
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")
        
        if password1 and password2 and password1 == password2:
            first_name = cleaned_data.get("first_name", "").lower()
            last_name = cleaned_data.get("last_name", "").lower()
            
            if (first_name and len(first_name) > 2 and first_name in password1.lower()) or \
               (last_name and len(last_name) > 2 and last_name in password1.lower()):
                self.add_error("password1", "Password should not contain your name.")

        if not address_line1:
            self.add_error("address_line1", "Address line 1 is required.")
        if not city:
            self.add_error("city", "City is required.")
        if not postcode:
            self.add_error("postcode", "Postcode is required.")

        address_components = [
            address_line1,
            address_line2,
            city,
            county,
            postcode,
            country or "UK",
        ]
        full_address = ", ".join(filter(None, address_components))

        if full_address.strip():
            try:
                geocode_result = geocode_address(full_address)
                cleaned_data["latitude"] = geocode_result["latitude"]
                cleaned_data["longitude"] = geocode_result["longitude"]
                logger.info(f"Geocoded address for user signup: {full_address}")
            except Exception as e:
                logger.error(f"Failed to geocode address for user signup: {e}")
                self.add_error(None, "Unable to geocode address. Location-based features may not work correctly.")
                
        return cleaned_data

    def save(self, commit=True):
        """Creates user account and profile, associates with agency if available"""
        user = super().save(commit=False)
        user.email = self.cleaned_data.get("email", "").strip().lower()
        user.role = "staff"

        if commit:
            try:
                user.save()
                assign_user_to_group(user, "Agency Staff")

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

                logger.info(f"New user created: {user.username}")
                
            except Exception as e:
                logger.error(f"Error creating user {user.username}: {e}")
                raise ValidationError(f"User creation failed: {str(e)}")

        return user


class InvitationForm(forms.ModelForm):
    """Form for sending email invitations to prospective staff members"""

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
            if hasattr(user, "profile") and user.profile.agency:
                self.initial["agency"] = user.profile.agency

        self.helper = FormHelper()
        self.helper.form_method = "post"
        self.helper.layout = Layout(
            "email",
            "agency",
        )

    def clean_email(self):
        """Checks for existing users and active invitations"""
        email = self.cleaned_data.get("email", "").strip().lower()
        if not email:
            raise ValidationError("Email is required.")
        if User.objects.filter(email=email).exists():
            raise ValidationError("A user with this email already exists.")
        if Invitation.objects.filter(email=email, is_active=True).exists():
            raise ValidationError("An active invitation for this email already exists.")
            
        domain = email.split('@')[-1]
        try:
            socket.gethostbyname(domain)
        except socket.gaierror:
            self.add_error(None, f"Warning: The domain '{domain}' might not exist. Please double-check your email.")
            
        return email


class AcceptInvitationForm(UserCreationForm):
    """Form for users to create accounts from received invitations"""

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
        help_text="Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only."
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
        )

    def clean_email(self):
        """Verifies email matches the invitation"""
        email = self.cleaned_data.get("email", "").strip().lower()
        if not email:
            raise ValidationError("Email is required.")
            
        if self.invitation and email != self.invitation.email:
            raise ValidationError("Email does not match the invitation.")
            
        return email
        
    def clean_username(self):
        """Checks username availability"""
        username = self.cleaned_data.get("username")
        if not username:
            raise ValidationError("Username is required.")
            
        if User.objects.filter(username=username).exists():
            raise ValidationError("This username is already taken. Please choose another.")
            
        return username
        
    def clean(self):
        """Validates invitation status and password security"""
        cleaned_data = super().clean()
        
        if self.invitation and self.invitation.is_expired():
            raise ValidationError("This invitation has expired. Please request a new invitation.")
            
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")
        
        if password1 and password2 and password1 == password2:
            username = cleaned_data.get("username", "").lower()
            if username and len(username) > 3 and username in password1.lower():
                self.add_error("password1", "Password should not contain your username.")
                
            first_name = cleaned_data.get("first_name", "").lower()
            last_name = cleaned_data.get("last_name", "").lower()
            
            if (first_name and len(first_name) > 2 and first_name in password1.lower()) or \
               (last_name and len(last_name) > 2 and last_name in password1.lower()):
                self.add_error("password1", "Password should not contain your name.")
                
        return cleaned_data

    def save(self, commit=True):
        """Creates user account, assigns to appropriate group, and links to agency"""
        user = super().save(commit=False)
        user.email = self.cleaned_data.get("email", "").strip().lower()
        user.first_name = self.cleaned_data.get("first_name", "").strip()
        user.last_name = self.cleaned_data.get("last_name", "").strip()
        user.role = "staff"

        if commit:
            try:
                user.save()
                
                assign_user_to_group(user, "Agency Staff")

                if self.invitation and self.invitation.agency:
                    profile, created = Profile.objects.get_or_create(user=user)
                    profile.agency = self.invitation.agency
                    
                    profile.travel_radius = 0.0
                    profile.save()

                if self.invitation:
                    self.invitation.is_active = False
                    self.invitation.accepted_at = timezone.now()
                    self.invitation.save()

                logger.info(f"Invitation accepted by user: {user.username}")

                if self.request:
                    login(self.request, user)
                    
            except Exception as e:
                logger.error(f"Error creating user from invitation: {e}")
                raise ValidationError(f"Account creation failed: {str(e)}")

        return user


class ProfilePictureForm(forms.ModelForm):
    """Form for uploading and validating profile pictures"""

    class Meta:
        model = Profile
        fields = ["profile_picture"]
        widgets = {
            "profile_picture": forms.ClearableFileInput(
                attrs={
                    "class": "form-control-file",
                    "id": "id_profile_picture",
                    "accept": "image/jpeg,image/png,image/gif",
                }
            ),
        }

    def clean_profile_picture(self):
        """Validates image type, size, and dimensions"""
        if self.data.get('profile_picture-clear') == 'on':
            logger.info("Profile picture cleared by user")
            return None
            
        picture = self.cleaned_data.get("profile_picture", False)
        if not picture:
            return self.instance.profile_picture if hasattr(self.instance, 'profile_picture') else None
            
        max_file_size = 5 * 1024 * 1024
        if picture.size > max_file_size:
            logger.warning(f"Rejected oversized profile picture: {picture.size} bytes")
            raise ValidationError("Image file too large (maximum 5MB allowed).")

        try:
            file_extension = picture.name.split('.')[-1].lower()
            if file_extension not in ["jpg", "jpeg", "png", "gif"]:
                logger.warning(f"Rejected file with invalid extension: {file_extension}")
                raise ValidationError(f"Unsupported file extension: {file_extension}. Only JPEG, PNG, and GIF are allowed.")
            
            img = Image.open(picture)
            img_format = img.format.lower() if img.format else ''
            
            if img_format not in ["jpeg", "png", "gif"]:
                logger.warning(f"Rejected unsupported format: {img_format}")
                raise ValidationError("Unsupported file type. Only JPEG, PNG, and GIF are allowed.")
                
            width, height = img.size
            if width > 2000 or height > 2000:
                logger.warning(f"Rejected oversized dimensions: {width}x{height}")
                raise ValidationError("Image dimensions should not exceed 2000x2000 pixels.")
                
            img.thumbnail((100, 100))
            picture.seek(0)
                
        except Image.UnidentifiedImageError:
            logger.error(f"Could not identify image format for file: {picture.name}")
            raise ValidationError("The uploaded file is not a valid image.")
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Image processing error: {e}")
            raise ValidationError(f"Invalid image file: {e}. Please upload a valid image.")
            
        logger.debug(f"Profile picture validated: {picture.name, picture.size} bytes")
        return picture


class UpdateProfileForm(AddressFormMixin, forms.ModelForm):
    """Form for updating user profile and address information"""

    # Agency phone field for owners/managers
    agency_phone_number = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Agency phone number (UK format)",
                "id": "id_agency_phone_number",
            }
        ),
    )

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
                    "autocomplete": "address-level1",
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
            "travel_radius": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": "0",
                    "placeholder": "Travel Radius (miles)",
                    "id": "id_travel_radius",
                }
            ),
            "latitude": forms.HiddenInput(
                attrs={"id": "id_latitude"},
            ),
            "longitude": forms.HiddenInput(
                attrs={"id": "id_longitude"},
            ),
        }

    def __init__(self, *args, **kwargs):
        super(UpdateProfileForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = "post"
        for field in ['address_line1', 'city', 'postcode']:
            if field in self.fields:
                self.fields[field].widget.attrs['required'] = 'required'
        
        user = self.instance.user if self.instance else None
        show_agency_phone = False
        
        if user:
            if hasattr(user, 'owned_agency') and user.owned_agency:
                show_agency_phone = True
                self.fields['agency_phone_number'].initial = user.owned_agency.phone_number
            elif user.groups.filter(name__in=["Agency Managers", "Agency Owners"]).exists() and user.profile.agency:
                show_agency_phone = True
                self.fields['agency_phone_number'].initial = user.profile.agency.phone_number
        
        if show_agency_phone:
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
                    Column("agency_phone_number", css_class="form-group col-md-6 mb-0"),
                ),
                "travel_radius",
                Field("latitude"),
                Field("longitude"),
            )
        else:
            self.fields.pop('agency_phone_number')
            self.helper.layout = Layout(
                "address_line1",
                "address_line2",
                Row(
                    Column("city", css_class="form-group col-md-4 mb-0"),
                    Column("county", css_class="form-group col-md-4 mb-0"),
                    Column("postcode", css_class="form-group col-md-4 mb-0"),
                ),
                "country",
                "travel_radius",
                Field("latitude"),
                Field("longitude"),
            )

    def clean_agency_phone_number(self):
        """Validates UK phone number format"""
        phone_number = self.cleaned_data.get("agency_phone_number")
        if phone_number:
            return validate_uk_phone_number(phone_number)
        return phone_number

    def clean_travel_radius(self):
        """Validates travel radius limits (0-50 miles)"""
        travel_radius = self.cleaned_data.get("travel_radius")
        if travel_radius is None:
            return 0.0
        if travel_radius < 0 or travel_radius > 50:
            raise ValidationError("Travel radius must be between 0 and 50 miles.")
        return travel_radius

    def save(self, commit=True):
        """Updates profile and agency phone if user has permissions"""
        profile = super().save(commit=False)
        
        user = profile.user
        agency_phone = self.cleaned_data.get('agency_phone_number')
        
        if agency_phone and hasattr(user, 'owned_agency') and user.owned_agency:
            agency = user.owned_agency
            agency.phone_number = agency_phone
            if commit:
                agency.save()
        elif agency_phone and user.groups.filter(name__in=["Agency Managers", "Agency Owners"]).exists() and profile.agency:
            agency = profile.agency
            agency.phone_number = agency_phone
            if commit:
                agency.save()
                
        if commit:
            profile.save()
            
        return profile


class UserForm(UserCreationForm):
    """Admin form for creating user accounts with group assignment"""

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
        """Validates email uniqueness and DNS record existence"""
        email = self.cleaned_data.get("email", "").strip().lower()
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("A user with this email already exists.")
            
        domain = email.split('@')[-1]
        try:
            socket.gethostbyname(domain)
        except socket.gaierror:
            self.add_error(None, f"Warning: The domain '{domain}' might not exist. Please double-check your email.")
            
        return email
        
    def clean(self):
        """Validates password security against username and name inclusion"""
        cleaned_data = super().clean()
        
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")
        
        if password1 and password2 and password1 == password2:
            username = cleaned_data.get("username", "").lower()
            if username and len(username) > 3 and username in password1.lower():
                self.add_error("password1", "Password should not contain your username.")
                
            first_name = cleaned_data.get("first_name", "").lower()
            last_name = cleaned_data.get("last_name", "").lower()
            
            if (first_name and len(first_name) > 2 and first_name in password1.lower()) or \
               (last_name and len(last_name) > 2 and last_name in password1.lower()):
                self.add_error("password1", "Password should not contain your name.")
                
        return cleaned_data


class UserUpdateForm(UserChangeForm):
    """Admin form for updating user accounts without password changes"""

    password = None  # Exclude password field

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

    def clean_email(self):
        """Validates email uniqueness and DNS record existence"""
        email = self.cleaned_data.get("email", "").strip().lower()
        if User.objects.filter(email=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("This email is already in use.")
            
        domain = email.split('@')[-1]
        try:
            socket.gethostbyname(domain)
        except socket.gaierror:
            self.add_error(None, f"Warning: The domain '{domain}' might not exist. Please double-check your email.")
            
        return email


class StaffCreationForm(AddressFormMixin, UserCreationForm):
    """Form for agency managers to create staff accounts with address info"""

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
        widget=forms.NumberInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter travel radius (in miles)",
                "id": "id_travel_radius",
            }
        ),
        help_text="Maximum distance the staff member is willing to travel for shifts (in miles)."
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
                "autocomplete": "address-level1",
                "id": "id_county",
            }
        ),
    )
    country = forms.CharField(
        max_length=100,
        required=False,
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

    def clean_email(self):
        """Checks for existing users and active invitations"""
        email = self.cleaned_data.get("email", "").strip().lower()
        if not email:
            raise ValidationError("Email is required.")
        if User.objects.filter(email=email).exists():
            raise ValidationError("A user with this email already exists.")
        if Invitation.objects.filter(email=email, is_active=True).exists():
            raise ValidationError("An active invitation for this email already exists.")
            
        domain = email.split('@')[-1]
        try:
            socket.gethostbyname(domain)
        except socket.gaierror:
            self.add_error(None, f"Warning: The domain '{domain}' might not exist. Please double-check your email.")
            
        return email

    def clean_travel_radius(self):
        """Validates travel radius limits (0-50 miles)"""
        travel_radius = self.cleaned_data.get("travel_radius")
        if travel_radius is None:
            return 0.0
        if travel_radius < 0 or travel_radius > 50:
            raise ValidationError("Travel radius must be between 0 and 50 miles.")
        return travel_radius

    def clean_postcode(self):
        """Validates UK postcode format"""
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

    def clean(self):
        """Validates password security and geocodes address"""
        cleaned_data = super().clean()
        address_line1 = cleaned_data.get("address_line1")
        address_line2 = cleaned_data.get("address_line2")
        city = cleaned_data.get("city")
        county = cleaned_data.get("county")
        postcode = cleaned_data.get("postcode")
        country = cleaned_data.get("country")
        
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")
        
        if password1 and password2 and password1 == password2:
            username = cleaned_data.get("username", "").lower()
            first_name = cleaned_data.get("first_name", "").lower()
            last_name = cleaned_data.get("last_name", "").lower()
            
            if username and len(username) > 3 and username in password1.lower():
                self.add_error("password1", "Password should not contain the username.")
                
            if (first_name and len(first_name) > 2 and first_name in password1.lower()) or \
               (last_name and len(last_name) > 2 and last_name in password1.lower()):
                self.add_error("password1", "Password should not contain the name.")

        if not address_line1:
            self.add_error("address_line1", "Address line 1 is required.")
        if not city:
            self.add_error("city", "City is required.")
        if not postcode:
            self.add_error("postcode", "Postcode is required.")

        address_components = [
            address_line1,
            address_line2,
            city,
            county,
            postcode,
            country,
        ]
        full_address = ", ".join(filter(None, address_components))

        if full_address.strip():
            try:
                geocode_result = geocode_address(full_address)
                cleaned_data["latitude"] = geocode_result["latitude"]
                cleaned_data["longitude"] = geocode_result["longitude"]
                logger.info(
                    f"Geocoded address for invitation acceptance: {full_address}"
                )
            except Exception as e:
                logger.error(
                    f"Failed to geocode address for invitation acceptance: {e}"
                )
                self.add_error(None, "Unable to geocode address. Location-based features may not work correctly.")
        
        return cleaned_data

    def save(self, commit=True):
        """Creates staff account and links to agency"""
        user = super().save(commit=False)
        user.email = self.cleaned_data.get("email", "").strip().lower()
        user.role = "staff"

        if commit:
            try:
                user.save()
                assign_user_to_group(user, "Agency Staff")

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
                    profile.save()

                logger.info(f"New staff member created: {user.username}")
                
            except Exception as e:
                logger.error(f"Error creating staff member: {e}")
                raise ValidationError(f"Staff member creation failed: {str(e)}")

        return user


class StaffUpdateForm(AddressFormMixin, forms.ModelForm):
    """Form for updating staff member details and address"""

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
        widget=forms.NumberInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter travel radius (in miles)",
                "id": "id_travel_radius",
            }
        ),
    )

    # Address fields
    address_line1 = forms.CharField(
        max_length=255,
        required=False,
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
        required=False,
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
                "autocomplete": "address-level1",
                "id": "id_county",
            }
        ),
    )
    country = forms.CharField(
        max_length=100,
        required=False,
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
        required=False,
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
        super(StaffUpdateForm, self).__init__(*args, **kwargs)
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
        
        if self.instance and hasattr(self.instance, 'profile'):
            profile = self.instance.profile
            self.initial.update({
                'travel_radius': profile.travel_radius,
                'address_line1': profile.address_line1,
                'address_line2': profile.address_line2,
                'city': profile.city,
                'county': profile.county,
                'country': profile.country,
                'postcode': profile.postcode,
                'latitude': profile.latitude,
                'longitude': profile.longitude,
            })

    def clean_email(self):
        """Validates email uniqueness and DNS record existence"""
        email = self.cleaned_data.get("email", "").strip().lower()
        if User.objects.filter(email=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("This email is already in use.")
            
        domain = email.split('@')[-1]
        try:
            socket.gethostbyname(domain)
        except socket.gaierror:
            self.add_error(None, f"Warning: The domain '{domain}' might not exist. Please double-check your email.")
            
        return email

    def clean_travel_radius(self):
        """Validates travel radius limits (0-50 miles)"""
        travel_radius = self.cleaned_data.get("travel_radius")
        if travel_radius is None:
            return 0.0
        if travel_radius < 0 or travel_radius > 50:
            raise ValidationError("Travel radius must be between 0 and 50 miles.")
        return travel_radius

    def clean_postcode(self):
        """Validates UK postcode format"""
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

    def clean(self):
        """Geocodes address if fields are provided"""
        cleaned_data = super().clean()
        address_line1 = cleaned_data.get("address_line1")
        address_line2 = cleaned_data.get("address_line2")
        city = cleaned_data.get("city")
        county = cleaned_data.get("county")
        postcode = cleaned_data.get("postcode")
        country = cleaned_data.get("country")

        if address_line1 or city or postcode:
            address_components = [
                address_line1,
                address_line2,
                city,
                county,
                postcode,
                country,
            ]
            full_address = ", ".join(filter(None, address_components))

            if full_address.strip():
                try:
                    geocode_result = geocode_address(full_address)
                    cleaned_data["latitude"] = geocode_result["latitude"]
                    cleaned_data["longitude"] = geocode_result["longitude"]
                    logger.info(f"Geocoded address for staff update: {full_address}")
                except Exception as e:
                    logger.error(f"Failed to geocode address for staff update: {e}")
                    self.add_error(None, "Unable to geocode address. Location-based features may not work correctly.")
                    
        return cleaned_data

    def save(self, commit=True):
        """Updates user and profile information"""
        user = super().save(commit=False)
        user.email = self.cleaned_data.get("email", "").strip().lower()

        if commit:
            try:
                user.save()
                profile, created = Profile.objects.get_or_create(user=user)
                profile.travel_radius = self.cleaned_data.get("travel_radius") or 0.0
                address_line1 = self.cleaned_data.get("address_line1")
                if address_line1:
                    profile.address_line1 = address_line1
                    profile.address_line2 = self.cleaned_data.get("address_line2")
                    profile.city = self.cleaned_data.get("city")
                    profile.county = self.cleaned_data.get("county")
                    profile.country = self.cleaned_data.get("country") or "UK"
                    profile.postcode = self.cleaned_data.get("postcode")
                    profile.latitude = self.cleaned_data.get("latitude")
                    profile.longitude = self.cleaned_data.get("longitude")
                profile.save()

                logger.info(f"Staff member updated: {user.username}")
                
            except Exception as e:
                logger.error(f"Error updating staff member {user.username}: {e}")
                raise ValidationError(f"Staff member update failed: {str(e)}")

        return user


class ActivateTOTPForm(forms.Form):
    """Form for enabling two-factor authentication"""

    totp_code = forms.CharField(
        max_length=6,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter code from authenticator",
                "id": "id_totp_code",
            }
        ),
        label="Enter TOTP Code",
    )
    
    def clean_totp_code(self):
        """Validates TOTP code format (6 digits)"""
        code = self.cleaned_data.get("totp_code", "").strip()
        if not code:
            raise ValidationError("TOTP code is required.")
        
        if not code.isdigit() or len(code) != 6:
            raise ValidationError("TOTP code must be 6 digits.")
            
        return code


class RecoveryCodeForm(forms.Form):
    """Form for using 2FA recovery codes"""

    recovery_code = forms.CharField(
        max_length=8,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Recovery Code",
                "id": "id_recovery_code",
            }
        ),
        label="Recovery Code",
    )
    
    def clean_recovery_code(self):
        """Validates recovery code format (8 alphanumeric chars)"""
        code = self.cleaned_data.get("recovery_code", "").strip().upper()
        if not code:
            raise ValidationError("Recovery code is required.")
            
        if len(code) != 8 or not all(c.isalnum() for c in code):
            raise ValidationError("Invalid recovery code format. Please enter a valid 8-character code.")
            
        return code


class MFAForm(forms.Form):
    """Form for entering MFA codes during login"""

    totp_code = forms.CharField(
        max_length=6,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter MFA code",
                "id": "id_totp_code",
                "autofocus": "autofocus",
            }
        ),
        label="MFA Code",
    )
    
    def clean_totp_code(self):
        """Validates TOTP code format (6 digits)"""
        code = self.cleaned_data.get("totp_code", "").strip()
        if not code:
            raise ValidationError("MFA code is required.")
        
        if not code.isdigit() or len(code) != 6:
            raise ValidationError("MFA code must be 6 digits.")
            
        return code