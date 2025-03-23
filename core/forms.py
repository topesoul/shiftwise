# /workspace/shiftwise/core/forms.py

import re
import logging
from django import forms
from django.core.exceptions import ValidationError
from shiftwise.utils import geocode_address

logger = logging.getLogger(__name__)

class AddressFormMixin:
    """
    Mixin for standardized address validation across forms.
    Provides validation for UK addresses and geocoding functionality.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Mark mandatory address fields as required in the UI
        for field_name in ['address_line1', 'city', 'postcode']:
            if field_name in self.fields:
                self.fields[field_name].required = True
                if 'class' in self.fields[field_name].widget.attrs:
                    self.fields[field_name].widget.attrs['class'] += ' required'
                else:
                    self.fields[field_name].widget.attrs['class'] = 'required'

    def clean_address_line1(self):
        address_line1 = self.cleaned_data.get("address_line1", "").strip()
        if not address_line1:
            raise ValidationError("Address line 1 is required.")
        return address_line1

    def clean_city(self):
        city = self.cleaned_data.get("city", "").strip()
        if not city:
            raise ValidationError("City is required.")
        return city

    def clean_postcode(self):
        """Ensures postcode follows UK format standards"""
        postcode = self.cleaned_data.get("postcode", "").strip()
        if not postcode:
            raise ValidationError("Postcode is required.")
            
        uk_postcode_regex = r"^[A-Z]{1,2}\d[A-Z\d]? ?\d[A-Z]{2}$"
        if not re.match(uk_postcode_regex, postcode.upper()):
            raise ValidationError("Enter a valid UK postcode.")
        return postcode.upper()

    def clean_latitude(self):
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

    def clean(self):
        """
        Geocodes address when valid and coordinates aren't provided.
        Continues form processing even if geocoding fails.
        """
        cleaned_data = super().clean()
        
        # Proceed with geocoding only if address fields are valid
        if not self.errors and all(k in cleaned_data for k in ['address_line1', 'city', 'postcode']):
            if not (cleaned_data.get("latitude") and cleaned_data.get("longitude")):
                address_components = [
                    cleaned_data.get("address_line1"),
                    cleaned_data.get("address_line2", ""),
                    cleaned_data.get("city"),
                    cleaned_data.get("county", ""),
                    cleaned_data.get("postcode"),
                    cleaned_data.get("country", "UK"),
                ]
                full_address = ", ".join(filter(None, address_components))
                
                try:
                    geocode_result = geocode_address(full_address)
                    cleaned_data["latitude"] = geocode_result["latitude"]
                    cleaned_data["longitude"] = geocode_result["longitude"]
                    logger.info(f"Geocoded address: {full_address}")
                except Exception as e:
                    logger.error(f"Failed to geocode address: {e}")
                    self.add_error(None, "Unable to geocode address. Location-based features may not work correctly.")
        
        return cleaned_data
