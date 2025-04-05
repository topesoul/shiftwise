// /static/js/profile.js

// Profile page enhancements for form validation and address functionality
document.addEventListener('DOMContentLoaded', function() {
    const profileModal = document.getElementById('updateProfileModal');
    const profileForm = profileModal ? profileModal.querySelector('form') : null;
    const profileData = document.getElementById('profile-data');

    console.log("Profile.js loaded");

    // Display modal if server-side validation detected errors
    if (profileData && profileData.dataset.hasErrors === 'true') {
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
            // Block invalid form submission and focus first error
            if (!profileForm.checkValidity() || !validateProfileForm(profileForm)) {
                event.preventDefault();
                event.stopPropagation();

                if (typeof $ !== 'undefined') {
                    $('#updateProfileModal').modal('show');
                }

                const firstInvalid = profileForm.querySelector('.is-invalid') ||
                    profileForm.querySelector(':invalid');
                if (firstInvalid) {
                    firstInvalid.focus();
                }
            }
        });

        // Real-time field validation
        profileForm.querySelectorAll('input, select, textarea').forEach(function(field) {
            field.addEventListener('blur', function() {
                validateField(field);
            });

            field.addEventListener('change', function() {
                validateField(field);
            });
        });
    }

    // Initialize Google Maps address autocomplete when modal opens
    if (profileModal && typeof $ !== 'undefined') {
        $(profileModal).on('shown.bs.modal', function() {
            setTimeout(function() {
                if (window.google && window.google.maps && window.google.maps.places) {
                    const addressFields = profileModal.querySelectorAll('.address-autocomplete');
                    
                    for (let i = 0; i < addressFields.length; i++) {
                        const field = addressFields[i];
                        
                        // Try using global autocomplete functions first
                        if (typeof window.setupAutocomplete === 'function') {
                            window.setupAutocomplete(field);
                        } 
                        else if (typeof window.setupAddressField === 'function') {
                            window.setupAddressField(field);
                        }
                        // Fallback implementation if global functions unavailable
                        else {
                            try {
                                // Skip if already initialized
                                if (!field._hasAutocomplete) {
                                    const autocomplete = new google.maps.places.Autocomplete(field, {
                                        types: ['address'],
                                        componentRestrictions: { country: ['gb'] },
                                        fields: ['address_components', 'geometry', 'formatted_address']
                                    });
                                    
                                    field._hasAutocomplete = true;
                                    
                                    autocomplete.addListener('place_changed', function() {
                                        const place = autocomplete.getPlace();
                                        if (!place.geometry) return;
                                        
                                        const form = field.closest('form');
                                        if (!form) return;
                                        
                                        // Populate form fields with selected address
                                        const address1 = form.querySelector('#id_address_line1, [name="address_line1"]');
                                        const city = form.querySelector('#id_city, [name="city"]');
                                        const county = form.querySelector('#id_county, [name="county"]');
                                        const postcode = form.querySelector('#id_postcode, [name="postcode"]');
                                        
                                        if (address1) {
                                            const parts = place.formatted_address.split(',');
                                            address1.value = parts[0].trim();
                                        }
                                        
                                        if (city) {
                                            // Extract city from components or default to London
                                            let cityValue = '';
                                            
                                            for (const component of place.address_components) {
                                                if (component.types.includes('postal_town') && !cityValue) {
                                                    cityValue = component.long_name;
                                                }
                                                else if (component.types.includes('locality') && !cityValue) {
                                                    cityValue = component.long_name;
                                                }
                                            }
                                            
                                            city.value = cityValue || "London";
                                            
                                            if (city.value) {
                                                city.dispatchEvent(new Event('change', { bubbles: true }));
                                            }
                                        }
                                    });
                                }
                            } catch (e) {
                                console.error("Fallback autocomplete failed:", e);
                            }
                        }
                    }
                }
            }, 300);
        });
    }

    /**
     * Validates individual form field based on type and requirements
     */
    function validateField(field) {
        let isValid = true;

        field.classList.remove('is-invalid', 'is-valid');

        const feedback = field.nextElementSibling;
        if (feedback && feedback.classList.contains('invalid-feedback')) {
            feedback.style.display = 'none';
        }

        // Required field validation
        if (field.hasAttribute('required') && !field.value.trim()) {
            showFieldError(field, 'This field is required');
            isValid = false;
        }

        // UK postcode format validation
        if (field.id === 'id_postcode' && field.value.trim()) {
            const ukPostcodeRegex = /^[A-Z]{1,2}\d[A-Z\d]? ?\d[A-Z]{2}$/i;
            if (!ukPostcodeRegex.test(field.value.trim())) {
                showFieldError(field, 'Please enter a valid UK postcode');
                isValid = false;
            }
        }

        // UK phone number format validation
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
     * Validates entire form and adds error summary if needed
     */
    function validateProfileForm(form) {
        let isValid = true;

        const formFields = form.querySelectorAll('input, select, textarea');
        for (let i = 0; i < formFields.length; i++) {
            const fieldValid = validateField(formFields[i]);
            isValid = isValid && fieldValid;
        }

        // Add or remove validation summary message
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
     * Displays inline error for a form field
     */
    function showFieldError(field, message) {
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
