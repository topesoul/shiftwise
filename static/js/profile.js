// /static/js/profile.js

document.addEventListener('DOMContentLoaded', function() {
    // Debug Maps API status
    console.log("Profile.js loaded, Google Maps available:", 
        !!(window.google && window.google.maps && window.google.maps.places));
    
    // Setup address autocomplete functionality
    $('#updateProfileModal').on('shown.bs.modal', function() {
        console.log("Profile modal shown");
        
        if (window.google && window.google.maps && window.google.maps.places) {
            console.log("Initializing address autocomplete");
            initAutocomplete();
        } else {
            console.log("Maps API not available, setting up deferred initialization");
            
            document.addEventListener('google-maps-loaded', function handleGoogleMapsLoaded() {
                console.log("Maps API loaded, initializing autocomplete");
                initAutocomplete();
                document.removeEventListener('google-maps-loaded', handleGoogleMapsLoaded);
            });
        }
    });
    
    // Show modal if validation errors exist
    if (document.querySelector('.invalid-feedback.d-block') || 
        document.querySelector('.alert.alert-danger')) {
        $('#updateProfileModal').modal('show');
    }
    
    // Add visual styling to autocomplete fields
    const addressFields = document.querySelectorAll('.address-autocomplete');
    addressFields.forEach(field => {
        field.classList.add('address-field-with-autocomplete');
    });
});
