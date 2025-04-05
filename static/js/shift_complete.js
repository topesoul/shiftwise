// /workspace/shiftwise/static/js/shift_complete.js

document.addEventListener('DOMContentLoaded', function() {
    // Check for essential elements before proceeding
    const canvas = document.getElementById('signaturePad');
    if (!canvas) {
        console.error("SignaturePad canvas not found");
        return;
    }
    
    const signatureInput = document.querySelector('.signatureInput');
    const clearSignatureButton = document.querySelector('.clearSignature');
    const getLocationButton = document.querySelector('.getLocation');
    const locationStatus = document.getElementById('locationStatus');
    const confirmAddressInput = document.getElementById('id_confirm_address');
    const latitudeField = document.getElementById('id_shift_completion_latitude');
    const longitudeField = document.getElementById('id_shift_completion_longitude');
    
    // Check if all required elements exist
    if (!signatureInput || !clearSignatureButton || !getLocationButton || 
        !locationStatus || !confirmAddressInput || !latitudeField || !longitudeField) {
        console.error("Essential shift completion elements not found in the DOM");
        return;
    }
    
    // Signature pad setup with consistent configuration
    const signaturePad = new SignaturePad(canvas, {
        backgroundColor: 'rgb(255, 255, 255)',
        penColor: 'rgb(0, 0, 0)'
    });
    
    // Adjust canvas for device pixel ratio
    function resizeCanvas() {
        const ratio = Math.max(window.devicePixelRatio || 1, 1);
        canvas.width = canvas.offsetWidth * ratio;
        canvas.height = canvas.offsetHeight * ratio;
        canvas.getContext("2d").scale(ratio, ratio);
        signaturePad.clear();
    }
    
    // Initial canvas size
    resizeCanvas();
    window.addEventListener("resize", resizeCanvas);
    
    // Clear signature
    clearSignatureButton.addEventListener('click', function() {
        signaturePad.clear();
        signatureInput.value = "";
    });
    
    // Get location
    getLocationButton.addEventListener('click', function() {
        if (!navigator.geolocation) {
            locationStatus.innerHTML = '<span class="text-danger">Geolocation is not supported by your browser.</span>';
            return;
        }
        
        locationStatus.innerHTML = '<span class="text-info">Getting location...</span>';
        
        navigator.geolocation.getCurrentPosition(
            function(position) {
                const latitude = position.coords.latitude.toFixed(6);
                const longitude = position.coords.longitude.toFixed(6);
                latitudeField.value = latitude;
                longitudeField.value = longitude;
                locationStatus.innerHTML = `<span class="text-success">Location captured: (${latitude}, ${longitude})</span>`;
                
                // Fetch address using reverse geocoding
                fetch(`https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat=${latitude}&lon=${longitude}`)
                    .then((response) => response.json())
                    .then((data) => {
                        const address = data.display_name || "Address not found.";
                        confirmAddressInput.value = address;
                    })
                    .catch((error) => {
                        console.error("Error fetching address:", error);
                        confirmAddressInput.value = "Unable to retrieve address.";
                    });
            },
            function(error) {
                console.error("Error getting location:", error);
                let errorMessage = "Unable to retrieve your location.";
                
                switch(error.code) {
                    case error.PERMISSION_DENIED:
                        errorMessage = 'Location permission denied. Please allow location access.';
                        break;
                    case error.POSITION_UNAVAILABLE:
                        errorMessage = 'Location information unavailable.';
                        break;
                    case error.TIMEOUT:
                        errorMessage = 'Location request timed out.';
                        break;
                }
                locationStatus.innerHTML = `<span class="text-danger">${errorMessage}</span>`;
            },
            {
                enableHighAccuracy: true,
                timeout: 10000,
                maximumAge: 0
            }
        );
    });
    
    // Target form more specifically
    const completeShiftForm = document.querySelector('form[action*="complete"]') || 
                              document.querySelector('form[enctype="multipart/form-data"]') ||
                              document.querySelector('form');
    
    if (!completeShiftForm) {
        console.error("Could not find the shift completion form");
        return;
    }
    
    // Capture signature on submit
    completeShiftForm.addEventListener('submit', function(event) {
        // Check if signature is provided
        if (signaturePad.isEmpty()) {
            event.preventDefault();
            alert('Please provide a signature before submitting.');
            return;
        }
        
        // Capture signature data
        const signatureData = signaturePad.toDataURL('image/png');
        signatureInput.value = signatureData;
        
        // Check if location is provided
        if (!latitudeField.value || !longitudeField.value) {
            event.preventDefault();
            alert('Please capture your location before submitting.');
            return;
        }
        
        // Form is valid - allow submission
        console.log("Shift completion form validated successfully");
    });
});
