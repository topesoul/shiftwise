// /static/js/profile.js

/**
 * Profile page functionality:
 * - Handles modal display and persistence based on form validation status.
 * - Implements client-side form validation with real-time feedback.
 * - Initializes address auto-completion on modal display.
 */
document.addEventListener('DOMContentLoaded', function() {
    console.log("Profile.js loaded");

    const profileModal = document.getElementById('updateProfileModal');
    const profileForm = profileModal ? profileModal.querySelector('form') : null;
    const profileData = document.getElementById('profile-data');

    console.log("Profile modal found:", !!profileModal);
    console.log("Profile form found:", !!profileForm);
    console.log("Has errors:", profileData ? profileData.dataset.hasErrors : 'No profile data');

    // Show modal if the form contains errors from server-side validation.
    if (profileData && profileData.dataset.hasErrors === 'true') {
        console.log("Form has errors, showing modal");

        if (typeof $ !== 'undefined') {
            $('#updateProfileModal').modal({
                backdrop: 'static',
                keyboard: false,
                show: true
            });
        }
    }

    if (profileForm) {
        profileForm.addEventListener('submit', function(event) {
            console.log("Form submission attempted");

            if (!profileForm.checkValidity() || !validateProfileForm(profileForm)) {
                event.preventDefault();
                event.stopPropagation();

                console.log("Validation failed, keeping modal open");

                if (typeof $ !== 'undefined') {
                    $('#updateProfileModal').modal('show');
                }

                const firstInvalid = profileForm.querySelector('.is-invalid') ||
                    profileForm.querySelector(':invalid');
                if (firstInvalid) {
                    console.log("Focusing first invalid field:", firstInvalid.id || 'unnamed');
                    firstInvalid.focus();
                }
            } else {
                console.log("Form validation passed, submitting");
            }
        });

        profileForm.querySelectorAll('input, select, textarea').forEach(function(field) {
            field.addEventListener('blur', function() {
                validateField(field);
            });

            field.addEventListener('change', function() {
                validateField(field);
            });
        });
    }

    // Initialize address auto-completion when the modal is displayed.
    if (profileModal && typeof $ !== 'undefined') {
        $(profileModal).on('shown.bs.modal', function() {
            console.log("Profile modal shown, initializing address fields");

            setTimeout(function() {
                if (window.google && window.google.maps && window.google.maps.places) {
                    console.log("Google Maps available, setting up address fields");

                    const addressFields = profileModal.querySelectorAll('.address-autocomplete');
                    console.log("Found " + addressFields.length + " address fields in modal");

                    for (let i = 0; i < addressFields.length; i++) {
                        if (window.setupAddressField) {
                            window.setupAddressField(addressFields[i]);
                        } else {
                            console.error("setupAddressField function not available");
                        }
                    }
                } else {
                    console.log("Google Maps not yet available");
                }
            }, 300);
        });
    }

    /**
     * Validates a single form field.
     * @param {HTMLElement} field - The form field to validate.
     * @returns {boolean} - True if the field is valid, false otherwise.
     */
    function validateField(field) {
        let isValid = true;

        field.classList.remove('is-invalid', 'is-valid');

        const feedback = field.nextElementSibling;
        if (feedback && feedback.classList.contains('invalid-feedback')) {
            feedback.style.display = 'none';
        }

        if (field.hasAttribute('required') && !field.value.trim()) {
            showFieldError(field, 'This field is required');
            isValid = false;
        }

        if (field.id === 'id_postcode' && field.value.trim()) {
            const ukPostcodeRegex = /^[A-Z]{1,2}\d[A-Z\d]? ?\d[A-Z]{2}$/i;
            if (!ukPostcodeRegex.test(field.value.trim())) {
                showFieldError(field, 'Please enter a valid UK postcode');
                isValid = false;
            }
        }

        if (field.id === 'id_agency_phone_number' && field.value.trim()) {
            const cleanedNumber = field.value.replace(/[\s\-\(\)]/g, '');
            const ukPhoneRegex = /^(\+44\d{10}|0\d{10})$/;
            if (!ukPhoneRegex.test(cleanedNumber)) {
                showFieldError(field, 'Please enter a valid UK phone number');
                isValid = false;
            }
        }

        if (isValid && field.value.trim()) {
            field.classList.add('is-valid');
        }

        return isValid;
    }

    /**
     * Validates the entire profile form.
     * @param {HTMLFormElement} form - The form to validate.
     * @returns {boolean} - True if the form is valid, false otherwise.
     */
    function validateProfileForm(form) {
        let isValid = true;

        const formFields = form.querySelectorAll('input, select, textarea');
        for (let i = 0; i < formFields.length; i++) {
            const fieldValid = validateField(formFields[i]);
            isValid = isValid && fieldValid;
        }

        // Display a summary message if there are errors.
        let existingSummary = form.querySelector('.validation-summary');
        if (!isValid) {
            if (!existingSummary) {
                const summary = document.createElement('div');
                summary.className = 'alert alert-danger validation-summary mt-3 mb-3';
                summary.innerHTML = '<strong>Please correct the errors below before submitting.</strong>';

                const modalBody = form.querySelector('.modal-body');
                if (modalBody) {
                    modalBody.insertBefore(summary, modalBody.firstChild);
                } else {
                    form.insertBefore(summary, form.firstChild);
                }
            }
        } else if (existingSummary) {
            existingSummary.remove();
        }

        return isValid;
    }

    /**
     * Displays an error message for a specific form field.
     * @param {HTMLElement} field - The form field to display the error for.
     * @param {string} message - The error message to display.
     */
    function showFieldError(field, message) {
        console.log("Error in field " + (field.id || 'unnamed') + ": " + message);

        field.classList.add('is-invalid');

        let feedback = field.nextElementSibling;
        if (!feedback || !feedback.classList.contains('invalid-feedback')) {
            feedback = document.createElement('div');
            feedback.className = 'invalid-feedback';
            field.parentNode.insertBefore(feedback, field.nextSibling);
        }

        feedback.textContent = message;
        feedback.style.display = 'block';
    }
});
