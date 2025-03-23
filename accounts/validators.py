# accounts/validators.py

import re
import logging
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)

def validate_uk_phone_number(value):
    """
    Validates UK phone numbers in standard formats
    Accepts: +44 1234 567890, 01234 567890
    """
    if not value:
        return value
        
    # Remove formatting characters
    cleaned_number = re.sub(r'[\s\-\(\)]', '', value)
    
    # Check for valid UK format
    uk_pattern = r'^(\+44\d{10}|0\d{10})$'
    if not re.match(uk_pattern, cleaned_number):
        raise ValidationError("Enter a valid UK phone number (+44 XXXX XXXXXX or 0XXXX XXXXXX).")
    
    return value

def validate_required_address(address_line1, city=None, postcode=None):
    """
    Validates mandatory address fields
    Raises ValidationError with specific field details if validation fails
    """
    errors = {}
    
    # Normalize and strip inputs
    address_line1 = "" if address_line1 is None else str(address_line1).strip()
    city = "" if city is None else str(city).strip()
    postcode = "" if postcode is None else str(postcode).strip()
    
    if not address_line1:
        errors["address_line1"] = "Address line 1 is required."
    
    if city is not None and not city:
        errors["city"] = "City is required."
        
    if postcode is not None and not postcode:
        errors["postcode"] = "Postcode is required."
    
    if errors:
        raise ValidationError(errors)
