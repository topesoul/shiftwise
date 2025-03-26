// /static/js/address_autocomplete.js

/**
 * Address autocomplete functionality for UK addresses
 * Handles form field population with geocoded address data
 */

// Track API initialization state
window.googleMapsInitialized = false;

// Debug logger
function log(message, object) {
    console.log(message);
    if (object) {
        console.log(object);
    }
}

/**
 * Sets up autocomplete on address fields
 */
function initializeAutocomplete() {
    // Exit if API unavailable or already initialized
    if (!window.google || !window.google.maps || !window.google.maps.places) return;
    if (window.googleMapsInitialized) return;
    
    log("Google Maps API loaded successfully.");
    window.googleMapsInitialized = true;
    
    // Initialize existing address fields
    var addressFields = document.querySelectorAll('.address-autocomplete');
    log("Found " + addressFields.length + " address-autocomplete inputs.");
    
    addressFields.forEach(function(field) {
        setupAutocomplete(field);
    });
    
    // Handle dynamic fields in modals
    if (typeof jQuery !== 'undefined') {
        jQuery(document).on('shown.bs.modal', function(e) {
            const modal = e.target;
            const addressFields = modal.querySelectorAll('.address-autocomplete');
            if (addressFields.length > 0) {
                log("Modal shown with " + addressFields.length + " address fields");
                addressFields.forEach(setupAutocomplete);
            }
        });
    }
}

/**
 * Configures autocomplete for a single input field
 */
function setupAutocomplete(field) {
    if (field._hasAutocomplete) return;
    
    try {
        log("Initializing autocomplete for input ID: " + field.id);
        
        const autocomplete = new google.maps.places.Autocomplete(field, {
            types: ['address'],
            componentRestrictions: { country: ['gb'] },
            fields: ['address_components', 'geometry', 'formatted_address']
        });
        
        field._hasAutocomplete = true;
        
        autocomplete.addListener('place_changed', function() {
            log("Place changed for input ID: " + field.id);
            
            const place = autocomplete.getPlace();
            if (!place.geometry) return;
            
            log("Geocoded location: " + place.geometry.location.lat() + ", " + place.geometry.location.lng());
            log("Full place data:", place);
            
            const form = field.closest('form');
            if (!form) return;
            
            const fields = {
                address1: form.querySelector('#id_address_line1'),
                address2: form.querySelector('#id_address_line2'),
                city: form.querySelector('#id_city'),
                county: form.querySelector('#id_county'),
                postcode: form.querySelector('#id_postcode'),
                country: form.querySelector('#id_country'),
                latitude: form.querySelector('#id_latitude'),
                longitude: form.querySelector('#id_longitude')
            };
            
            log("Form fields found:", fields);
            
            // Reset form fields
            if (fields.address2) fields.address2.value = '';
            if (fields.city) fields.city.value = '';
            if (fields.county) fields.county.value = '';
            if (fields.postcode) fields.postcode.value = '';
            if (fields.country) fields.country.value = 'United Kingdom';
            
            // Parse formatted address
            var formattedAddress = place.formatted_address;
            log("Formatted address: " + formattedAddress);
            
            var addressParts = formattedAddress.split(',').map(function(part) {
                return part.trim();
            });
            log("Address parts:", addressParts);
            
            // Check for flat/apartment info
            var firstPart = addressParts[0];
            var hasFlatInfo = /^(flat|apartment|apt|unit|suite|no\.?|room)\s+\d+/i.test(firstPart) || 
                             /^\d+[a-z]?\s*,\s*\d+/i.test(firstPart);
            
            log("First part has flat info: " + hasFlatInfo);
            
            // Extract address components
            let streetNumber = '';
            let route = '';
            let subpremise = '';
            let city = '';
            
            place.address_components.forEach(function(component) {
                const types = component.types;
                
                if (types.includes('street_number')) {
                    streetNumber = component.long_name;
                } 
                else if (types.includes('route')) {
                    route = component.long_name;
                }
                else if (types.includes('subpremise')) {
                    subpremise = component.long_name;
                }
                else if (types.includes('postal_town')) {
                    city = component.long_name;
                    if (fields.city) fields.city.value = city;
                }
                else if (types.includes('locality') && !city) {
                    city = component.long_name;
                    if (fields.city && !fields.city.value) fields.city.value = city;
                }
                else if (types.includes('administrative_area_level_2') && fields.county) {
                    fields.county.value = component.long_name;
                }
                else if (types.includes('postal_code') && fields.postcode) {
                    fields.postcode.value = component.long_name;
                }
                else if (types.includes('country') && fields.country) {
                    fields.country.value = component.long_name;
                }
            });
            
            log("Extracted components:", {
                streetNumber: streetNumber,
                route: route,
                subpremise: subpremise,
                city: city
            });
            
            // Set address line 1
            if (fields.address1) {
                if (hasFlatInfo || subpremise) {
                    fields.address1.value = firstPart;
                    log("Using first part for address1: " + firstPart);
                } 
                else if (streetNumber && route) {
                    fields.address1.value = streetNumber + ' ' + route;
                    log("Using components for address1: " + fields.address1.value);
                }
                else if (route) {
                    fields.address1.value = route;
                    log("Using route only for address1: " + route);
                }
                else {
                    fields.address1.value = firstPart;
                    log("Fallback to first part for address1: " + firstPart);
                }
            }
            
            // Ensure city is populated
            if (fields.city && !fields.city.value) {
                log("City not populated from components, trying alternatives");
                
                if (addressParts.length >= 3) {
                    var potentialCity = addressParts[addressParts.length - 3];
                    if (potentialCity && !/^[A-Z]{1,2}\d/.test(potentialCity)) {
                        fields.city.value = potentialCity;
                        log("Using address part for city: " + potentialCity);
                    }
                }
                
                if (!fields.city.value && fields.county && fields.county.value) {
                    fields.city.value = fields.county.value;
                    log("Falling back to county for city: " + fields.county.value);
                }
                
                if (!fields.city.value) {
                    fields.city.value = "London";
                    log("Using default city: London");
                }
            }
            
            // Set coordinates
            if (fields.latitude && place.geometry && place.geometry.location) {
                fields.latitude.value = place.geometry.location.lat();
                log("Set latitude: " + fields.latitude.value);
            }
            if (fields.longitude && place.geometry && place.geometry.location) {
                fields.longitude.value = place.geometry.location.lng();
                log("Set longitude: " + fields.longitude.value);
            }
            
            log("Final field values:", {
                address1: fields.address1 ? fields.address1.value : null,
                city: fields.city ? fields.city.value : null,
                county: fields.county ? fields.county.value : null,
                postcode: fields.postcode ? fields.postcode.value : null
            });
            
            // Trigger change events
            Object.keys(fields).forEach(function(key) {
                if (fields[key]) {
                    var event = new Event('change', { bubbles: true });
                    fields[key].dispatchEvent(event);
                }
            });
        });
    } catch (error) {
        console.error("Error setting up autocomplete:", error);
    }
}

/**
 * Google Maps API callback handler
 */
function googleMapsCallback() {
    log("Google Maps callback executed");
    initializeAutocomplete();
    window.initializeAutocomplete = initializeAutocomplete;
}

// Global callback for Maps API
window.googleMapsCallback = googleMapsCallback;

// Initialize on DOM ready if Maps API is already loaded
document.addEventListener('DOMContentLoaded', function() {
    log("DOM content loaded");
    if (window.google && window.google.maps && window.google.maps.places) {
        log("Google Maps already loaded, initializing autocomplete");
        initializeAutocomplete();
    }
});
