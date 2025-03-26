// /static/js/agency_signup.js

/**
 * Agency Signup Module
 * Handles form validation and field synchronization
 */

// Track warnings to avoid duplicates
const shownWarnings = new Set();

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
    
    /**
     * Sets up email synchronization between personal and agency emails
     */
    function setupEmailSynchronization() {
        if (!personalEmail || !agencyEmail) return;
        
        // Legacy email auto-population 
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
        
        // Append toggle link after help text
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
            
            // Handle checkbox state changes
            emailCheckbox.addEventListener('change', function() {
                if (this.checked) {
                    // Store previous value and sync emails
                    agencyEmail.dataset.previousValue = agencyEmail.value;
                    agencyEmail.value = personalEmail.value;
                    agencyEmailField.style.display = 'none';
                } else {
                    // Restore visibility and previous value
                    agencyEmailField.style.display = '';
                    if (agencyEmail.dataset.previousValue) {
                        agencyEmail.value = agencyEmail.dataset.previousValue;
                    }
                }
            });
            
            // Keep emails in sync when checkbox is checked
            personalEmail.addEventListener('input', function() {
                if (emailCheckbox.checked) {
                    agencyEmail.value = this.value;
                }
            });
        }
    }
    
    /**
     * Sets up field validation events
     */
    function setupValidation() {
        // UK postcode formatting and validation
        if (postcodeField) {
            postcodeField.addEventListener('blur', function() {
                formatAndValidatePostcode(this);
            });
        }
        
        // UK phone validation
        if (phoneField) {
            phoneField.addEventListener('blur', function() {
                validateUKPhoneNumber(this);
            });
        }
        
        // Required field validation
        form.querySelectorAll('[required]').forEach(field => {
            field.addEventListener('blur', function() {
                validateRequired(this);
            });
        });
    }
    
    /**
     * Formats and validates UK postcode
     * @param {HTMLElement} field - The postcode input field
     * @returns {boolean} - Whether the field is valid
     */
    function formatAndValidatePostcode(field) {
        let value = field.value.trim().toUpperCase();
        
        // Format postcode with proper spacing
        if (value.length > 0 && !value.includes(' ')) {
            const parts = value.match(/^([A-Z]{1,2}\d[A-Z\d]?)(\d[A-Z]{2})$/);
            if (parts && parts.length === 3) {
                value = parts[1] + ' ' + parts[2];
                field.value = value;
            }
        }
        
        return validateUKPostcode(field);
    }
    
    /**
     * Validates UK postcode format
     * @param {HTMLElement} field - The postcode input field
     * @returns {boolean} - Whether the field is valid
     */
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
    
    /**
     * Validates UK phone number format
     * @param {HTMLElement} field - The phone input field
     * @returns {boolean} - Whether the field is valid
     */
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
    
    /**
     * Validates required field
     * @param {HTMLElement} field - The required input field
     * @returns {boolean} - Whether the field is valid
     */
    function validateRequired(field) {
        if (!field.value.trim()) {
            const fieldName = field.getAttribute('placeholder') || 
                             field.getAttribute('name') || 
                             field.closest('.form-group').querySelector('label')?.textContent || 
                             'This field';
                             
            showError(field, `${fieldName} is required.`);
            return false;
        } else {
            clearError(field);
            return true;
        }
    }
    
    /**
     * Validates field based on its type
     * @param {HTMLElement} field - The field to validate
     * @returns {boolean} - Whether the field is valid
     */
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
    
    /**
     * Sets up form submission validation
     */
    function setupFormSubmission() {
        form.addEventListener('submit', function(e) {
            let isValid = true;
            let firstInvalidField = null;
            
            // Check all required fields
            form.querySelectorAll('[required]').forEach(field => {
                const fieldValid = validateField(field);
                
                if (!fieldValid && !firstInvalidField) {
                    firstInvalidField = field;
                }
                
                isValid = isValid && fieldValid;
            });
            
            // Validate optional fields with content
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
            
            // Prevent submission if validation fails
            if (!isValid) {
                e.preventDefault();
                if (firstInvalidField) {
                    firstInvalidField.focus();
                    firstInvalidField.scrollIntoView({ behavior: 'smooth', block: 'center' });
                }
            }
        });
    }
    
    /**
     * Shows error message for a field
     * @param {HTMLElement} field - The field with error
     * @param {string} message - Error message to display
     */
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
    
    /**
     * Clears error for a field
     * @param {HTMLElement} field - The field to clear
     */
    function clearError(field) {
        field.classList.remove('is-invalid');
        field.classList.add('is-valid');
        
        let feedbackDiv = field.nextElementSibling;
        if (feedbackDiv && feedbackDiv.classList.contains('invalid-feedback')) {
            feedbackDiv.style.display = 'none';
        }
    }
    
    /**
     * Adds domain warning to the form
     * @param {string} message - The warning message
     */
    function addDomainWarning(message) {
        if (shownWarnings.has(message)) return;
        shownWarnings.add(message);
        
        const warningDiv = document.createElement('div');
        warningDiv.className = 'alert alert-warning';
        warningDiv.innerHTML = `<i class="fas fa-exclamation-triangle mr-2"></i>${message}`;
        
        const firstField = form.querySelector('.form-group');
        if (firstField) {
            form.insertBefore(warningDiv, firstField);
        }
    }
});