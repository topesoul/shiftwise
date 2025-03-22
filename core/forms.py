# /workspace/shiftwise/core/forms.py

import re
from decimal import Decimal, InvalidOperation

from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator

import logging

logger = logging.getLogger(__name__)


class AddressFormMixin:
    """
    Mixin to include common address validation methods across all forms.
    
    This mixin provides consistent address validation for all forms that require
    address information, ensuring uniformity across the application.
    """

    def clean_postcode(self):
        """
        Validates the postcode based on UK-specific formats.
        
        Returns:
            str: The validated and formatted postcode.
            
        Raises:
            ValidationError: If the postcode is not valid.
        """
        postcode = self.cleaned_data.get("postcode", "")
        if postcode:
            postcode = postcode.strip().upper()
            
            # UK postcode regex - validates standard UK postcode formats
            uk_postcode_regex = r"^[A-Z]{1,2}\d[A-Z\d]? ?\d[A-Z]{2}$"
            if not re.match(uk_postcode_regex, postcode):
                raise ValidationError("Enter a valid UK postcode (e.g., SW1A 1AA).")
                
            # Format postcode to ensure consistent spacing (e.g., "SW1A 1AA" instead of "SW1A1AA")
            if len(postcode) > 4 and " " not in postcode:
                inward_code = postcode[-3:]
                outward_code = postcode[:-3]
                postcode = f"{outward_code} {inward_code}"
                
        return postcode

    def clean_latitude(self):
        """
        Validates the latitude value is within valid range (-90 to 90 degrees).
        
        Returns:
            float: The latitude value or None if not provided.
            
        Raises:
            ValidationError: If the latitude value is invalid.
        """
        latitude = self.cleaned_data.get("latitude")
        if latitude is None:
            return None
            
        try:
            latitude = float(latitude)
            if not (-90 <= latitude <= 90):
                raise ValidationError("Latitude must be between -90 and 90 degrees.")
        except (ValueError, TypeError):
            raise ValidationError("Invalid latitude value. Please provide a valid number.")
            
        return latitude

    def clean_longitude(self):
        """
        Validates the longitude value is within valid range (-180 to 180 degrees).
        
        Returns:
            float: The longitude value or None if not provided.
            
        Raises:
            ValidationError: If the longitude value is invalid.
        """
        longitude = self.cleaned_data.get("longitude")
        if longitude is None:
            return None
            
        try:
            longitude = float(longitude)
            if not (-180 <= longitude <= 180):
                raise ValidationError("Longitude must be between -180 and 180 degrees.")
        except (ValueError, TypeError):
            raise ValidationError("Invalid longitude value. Please provide a valid number.")
            
        return longitude
        
    def clean_travel_radius(self):
        """
        Ensures that travel_radius is a valid decimal between 0 and 50 miles.
        
        Returns:
            Decimal: The travel radius value, defaulting to 0.0 if not provided.
            
        Raises:
            ValidationError: If the travel radius is invalid.
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
        
    def clean_phone_number(self):
        """
        Validates and formats phone numbers.
        
        Returns:
            str: The validated and formatted phone number or empty string.
            
        Raises:
            ValidationError: If the phone number is invalid.
        """
        phone = self.cleaned_data.get("phone_number", "")
        if not phone:
            return ""
            
        # Remove spaces and non-numeric characters for validation
        phone_digits = re.sub(r'\D', '', phone)
        
        # Check length
        if len(phone_digits) < 10 or len(phone_digits) > 15:
            raise ValidationError("Phone number must be between 10 and 15 digits.")
            
        # Format UK numbers
        if phone_digits.startswith('44') and len(phone_digits) >= 12:
            # Format as +44 XXXX XXXXXX
            formatted = f"+{phone_digits[0:2]} {phone_digits[2:6]} {phone_digits[6:]}"
            return formatted
        elif phone_digits.startswith('0') and len(phone_digits) >= 11:
            # Format as 0XXXX XXXXXX
            formatted = f"{phone_digits[0:5]} {phone_digits[5:]}"
            return formatted
            
        # Return cleaned but unformatted number
        return phone_digits
        
    def validate_address(self):
        """
        Validates address fields as a group and logs validation issues.
        Does not raise exceptions but adds form errors instead.
        
        Returns:
            bool: True if validation passes, False otherwise.
        """
        address_line1 = self.cleaned_data.get("address_line1")
        city = self.cleaned_data.get("city")
        postcode = self.cleaned_data.get("postcode")
        
        validation_passed = True
        
        # Check required fields
        if not address_line1:
            self.add_error("address_line1", "Address line 1 is required.")
            validation_passed = False
            
        if not city:
            self.add_error("city", "City is required.")
            validation_passed = False
            
        if not postcode:
            self.add_error("postcode", "Postcode is required.")
            validation_passed = False
            
        return validation_passed