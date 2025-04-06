// /static/js/agency_signup.js

/**
 * Agency Signup Module
 */

document.addEventListener('DOMContentLoaded', function() {
    // Cache DOM elements
    const form = document.getElementById('agency-signup-form');
    if (!form) return;
    
    const personalEmail = document.getElementById('id_email');
    const agencyEmail = document.getElementById('id_agency_email');
    const postcodeField = document.getElementById('id_postcode');
    const phoneField = document.getElementById('id_agency_phone_number');
    const emailCheckbox = document.getElementById('use_same_email');
    const agencyEmailField = agencyEmail ? agencyEmail.closest('.form-group') : null;
    
    // Email synchronization
    setupEmailSynchronization();
    
    // Validation event listeners
    setupValidation();
    
    // Form submission validation
    setupFormSubmission();
    
    function setupEmailSynchronization() {
        if (!personalEmail || !agencyEmail) return;
        
        personalEmail.addEventListener('change', function() {
            if (!agencyEmail.value) {
                agencyEmail.value = personalEmail.value;
            }
        });
        
        // Email toggle link
        const toggleLink = document.createElement('a');
        toggleLink.href = '#';
        toggleLink.className = 'small ml-2';
        toggleLink.textContent = 'Use same as personal email';
        toggleLink.addEventListener('click', function(e) {
            e.preventDefault();
            agencyEmail.value = personalEmail.value;
            validateField(agencyEmail);
        });
        
        const helpText = agencyEmail.closest('.form-group').querySelector('small.text-muted');
        if (helpText) {
            helpText.parentNode.insertBefore(toggleLink, helpText.nextSibling);
        }
        
        // Checkbox for using same email
        if (emailCheckbox && agencyEmailField) {
            // Initialize checkbox state
            if (personalEmail.value && agencyEmail.value && 
                personalEmail.value.toLowerCase() === agencyEmail.value.toLowerCase()) {
                emailCheckbox.checked = true;
                agencyEmailField.style.display = 'none';
            }
            
            emailCheckbox.addEventListener('change', function() {
                if (this.checked) {
                    agencyEmail.dataset.previousValue = agencyEmail.value;
                    agencyEmail.value = personalEmail.value;
                    agencyEmailField.style.display = 'none';
                } else {
                    agencyEmailField.style.display = '';
                    if (agencyEmail.dataset.previousValue) {
                        agencyEmail.value = agencyEmail.dataset.previousValue;
                    }
                }
            });
            
            personalEmail.addEventListener('input', function() {
                if (emailCheckbox.checked) {
                    agencyEmail.value = this.value;
                }
            });
        }
    }
    
    function setupValidation() {
        if (postcodeField) {
            postcodeField.addEventListener('blur', function() {
                formatAndValidatePostcode(this);
            });
        }
        
        if (phoneField) {
            phoneField.addEventListener('blur', function() {
                validateUKPhoneNumber(this);
            });
        }
        
        form.querySelectorAll('[required]').forEach(field => {
            field.addEventListener('blur', function() {
                validateRequired(this);
            });
        });
    }
    
    function formatAndValidatePostcode(field) {
        let value = field.value.trim().toUpperCase();
        
        if (value.length > 0 && !value.includes(' ')) {
            const parts = value.match(/^([A-Z]{1,2}\d[A-Z\d]?)(\d[A-Z]{2})$/);
            if (parts && parts.length === 3) {
                value = parts[1] + ' ' + parts[2];
                field.value = value;
            }
        }
        
        return validateUKPostcode(field);
    }
    
    function validateUKPostcode(field) {
        const value = field.value.trim();
        if (value) {
            const ukPostcodeRegex = /^[A-Z]{1,2}\d[A-Z\d]? ?\d[A-Z]{2}$/i;
            const isValid = ukPostcodeRegex.test(value);
            
            if (!isValid) {
                showError(field, 'Enter a valid UK postcode (e.g., NE1 1AA)');
                return false;
            } else {
                clearError(field);
                return true;
            }
        }
        return true;
    }
    
    function validateUKPhoneNumber(field) {
        const value = field.value.trim();
        if (value) {
            const cleanedNumber = value.replace(/[\s\-\(\)]/g, '');
            const ukPattern = /^(\+44\d{10}|0\d{10})$/;
            const isValid = ukPattern.test(cleanedNumber);
            
            if (!isValid) {
                showError(field, 'Enter a valid UK phone number (e.g., +44 1234 567890 or 01234 567890)');
                return false;
            } else {
                clearError(field);
                return true;
            }
        }
        return true;
    }
    
    function validateRequired(field) {
        if (!field.value.trim()) {
            const fieldName = field.getAttribute('placeholder') || 
                             field.getAttribute('name') || 
                             (field.closest('.form-group').querySelector('label') ? field.closest('.form-group').querySelector('label').textContent : '') || 
                             'This field';
                             
            showError(field, `${fieldName} is required.`);
            return false;
        } else {
            clearError(field);
            return true;
        }
    }
    
    function validateField(field) {
        if (field.id === 'id_postcode') {
            return validateUKPostcode(field);
        } else if (field.id === 'id_agency_phone_number') {
            return validateUKPhoneNumber(field);
        } else if (field.hasAttribute('required')) {
            return validateRequired(field);
        }
        return true;
    }
    
    function setupFormSubmission() {
        form.addEventListener('submit', function(e) {
            let isValid = true;
            let firstInvalidField = null;
            
            form.querySelectorAll('[required]').forEach(field => {
                const fieldValid = validateField(field);
                
                if (!fieldValid && !firstInvalidField) {
                    firstInvalidField = field;
                }
                
                isValid = isValid && fieldValid;
            });
            
            if (postcodeField && postcodeField.value) {
                const postcodeValid = validateUKPostcode(postcodeField);
                if (!postcodeValid && !firstInvalidField) {
                    firstInvalidField = postcodeField;
                }
                isValid = isValid && postcodeValid;
            }
            
            if (phoneField && phoneField.value) {
                const phoneValid = validateUKPhoneNumber(phoneField);
                if (!phoneValid && !firstInvalidField) {
                    firstInvalidField = phoneField;
                }
                isValid = isValid && phoneValid;
            }
            
            if (!isValid) {
                e.preventDefault();
                if (firstInvalidField) {
                    firstInvalidField.focus();
                    firstInvalidField.scrollIntoView({ behavior: 'smooth', block: 'center' });
                }
            }
        });
    }
    
    function showError(field, message) {
        let feedbackDiv = field.nextElementSibling;
        if (!feedbackDiv || !feedbackDiv.classList.contains('invalid-feedback')) {
            feedbackDiv = document.createElement('div');
            feedbackDiv.className = 'invalid-feedback';
            field.parentNode.insertBefore(feedbackDiv, field.nextSibling);
        }
        
        field.classList.add('is-invalid');
        field.classList.remove('is-valid');
        feedbackDiv.textContent = message;
        feedbackDiv.style.display = 'block';
    }
    
    function clearError(field) {
        field.classList.remove('is-invalid');
        field.classList.add('is-valid');
        
        let feedbackDiv = field.nextElementSibling;
        if (feedbackDiv && feedbackDiv.classList.contains('invalid-feedback')) {
            feedbackDiv.style.display = 'none';
        }
    }
});
