// /static/js/form_validation.js

/**
 * UK Address Form Validation.
 * Implements client-side validation for UK address forms.
 */

// Validate a UK postcode format.
function validateUKPostcode(postcode) {
    if (!postcode) return false;
    const ukPostcodeRegex = /^[A-Z]{1,2}\d[A-Z\d]? ?\d[A-Z]{2}$/i;
    return ukPostcodeRegex.test(postcode);
}

// Validate a UK phone number (supports +44 and 0 prefixes).
function validateUKPhoneNumber(phoneNumber) {
    if (!phoneNumber) return true; // Optional field
    const cleanedNumber = phoneNumber.replace(/[\s\-\(\)]/g, '');
    const ukPattern = /^(\+44\d{10}|0\d{10})$/;
    return ukPattern.test(cleanedNumber);
}

// Check if a required field has a non-empty value.
function validateRequired(value, fieldName) {
    if (!value || value.trim() === '') {
        return {
            valid: false,
            message: `${fieldName} is required.`
        };
    }
    return { valid: true };
}

// Update UI feedback for a form field.
function applyFieldValidation(field, isValid, message = '') {
    let feedbackElement = field.nextElementSibling;
    if (!feedbackElement || !feedbackElement.classList.contains('invalid-feedback')) {
        feedbackElement = document.createElement('div');
        feedbackElement.className = 'invalid-feedback';
        field.parentNode.insertBefore(feedbackElement, field.nextSibling);
    }
    
    if (!isValid) {
        field.classList.add('is-invalid');
        field.classList.remove('is-valid');
        feedbackElement.textContent = message;
        feedbackElement.style.display = 'block';
    } else {
        field.classList.remove('is-invalid');
        field.classList.add('is-valid');
        feedbackElement.style.display = 'none';
    }
    
    return isValid;
}

// Set up validation on all forms.
function initFormValidation() {
    document.querySelectorAll('form').forEach(form => {
        if (form.getAttribute('novalidate') === 'novalidate') return;
        
        form.addEventListener('submit', function(e) {
            let isValid = true;
            
            // Validate fields marked as required.
            form.querySelectorAll('[required]').forEach(field => {
                const result = validateRequired(field.value, field.getAttribute('placeholder') || field.name);
                if (!result.valid) {
                    isValid = false;
                    applyFieldValidation(field, false, result.message);
                }
            });
            
            // Validate UK postcode.
            const postcodeField = form.querySelector('#id_postcode');
            if (postcodeField && postcodeField.value) {
                const validPostcode = validateUKPostcode(postcodeField.value);
                applyFieldValidation(postcodeField, validPostcode, validPostcode ? '' : 'Enter a valid UK postcode.');
                if (!validPostcode) isValid = false;
            }
            
            // Validate UK phone number.
            const phoneField = form.querySelector('#id_phone_number, #id_agency_phone_number');
            if (phoneField && phoneField.value) {
                const validPhone = validateUKPhoneNumber(phoneField.value);
                applyFieldValidation(phoneField, validPhone, validPhone ? '' : 'Enter a valid UK phone number.');
                if (!validPhone) isValid = false;
            }
            
            // Prevent submission if any validations failed.
            if (!isValid) {
                e.preventDefault();
                const modal = form.closest('.modal');
                if (modal) {
                    $(modal).modal('show');
                }
            }
        });
    });
}

// Initialize validation when the DOM content is loaded.
document.addEventListener('DOMContentLoaded', initFormValidation);
