/* global SignaturePad */
// /workspace/shiftwise/static/js/shift_complete.js

document.addEventListener('DOMContentLoaded', function() {
    console.log('Shift completion script loaded');
    
    // Verify SignaturePad library is loaded
    if (typeof SignaturePad === 'undefined') {
        console.error('SignaturePad library not loaded!');
        if (window.messageUtil) {
            window.messageUtil.error('Error: Signature pad component could not be loaded.');
        }
        return;
    }
    
    // DOM element references
    const canvas = document.getElementById('signaturePad');
    console.log('SignaturePad canvas found:', !!canvas);
    if (!canvas) {
        console.error("SignaturePad canvas not found");
        if (window.messageUtil) {
            window.messageUtil.error('Error: Signature pad component not found.');
        }
        return;
    }
    
    const signatureInput = document.querySelector('.signatureInput');
    const clearSignatureButton = document.querySelector('.clearSignature');
    const getLocationButton = document.querySelector('.getLocation');
    const locationStatus = document.getElementById('locationStatus');
    const confirmAddressInput = document.getElementById('id_confirm_address');
    const latitudeField = document.getElementById('id_shift_completion_latitude');
    const longitudeField = document.getElementById('id_shift_completion_longitude');
    
    if (!signatureInput || !clearSignatureButton || !getLocationButton || 
        !locationStatus || !confirmAddressInput || !latitudeField || !longitudeField) {
        console.error("Essential shift completion elements not found in the DOM");
        if (window.messageUtil) {
            window.messageUtil.error('Error: Required form elements could not be found.');
        }
        return;
    }
    
    // Initialize signature pad
    const signaturePad = new SignaturePad(canvas, {
        backgroundColor: 'rgb(255, 255, 255)',
        penColor: 'rgb(0, 0, 0)'
    });
    
    // Optimize canvas for device pixel ratio to prevent blurry signatures
    function resizeCanvas() {
        const ratio = Math.max(window.devicePixelRatio || 1, 1);
        canvas.width = canvas.offsetWidth * ratio;
        canvas.height = canvas.offsetHeight * ratio;
        canvas.getContext("2d").scale(ratio, ratio);
        signaturePad.clear();
    }
    
    resizeCanvas();
    window.addEventListener("resize", resizeCanvas);
    
    clearSignatureButton.addEventListener('click', function() {
        signaturePad.clear();
        signatureInput.value = "";
    });
    
    getLocationButton.addEventListener('click', function() {
        if (!navigator.geolocation) {
            locationStatus.innerHTML = '<span class="text-danger">Geolocation is not supported by your browser.</span>';
            if (window.messageUtil) {
                window.messageUtil.error('Geolocation is not supported by your browser.');
            }
            return;
        }
        
        locationStatus.innerHTML = '<span class="text-info">Getting location...</span>';
        if (window.messageUtil) {
            window.messageUtil.info('Getting location...');
        }
        
        // Request precise location with tight timeout
        navigator.geolocation.getCurrentPosition(
            function(position) {
                const latitude = position.coords.latitude.toFixed(6);
                const longitude = position.coords.longitude.toFixed(6);
                latitudeField.value = latitude;
                longitudeField.value = longitude;
                locationStatus.innerHTML = `<span class="text-success">Location captured: (${latitude}, ${longitude})</span>`;
                
                if (window.messageUtil) {
                    window.messageUtil.success('Location captured successfully.');
                }
                
                // Reverse geocode coordinates to human-readable address
                fetch(`https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat=${latitude}&lon=${longitude}`)
                    .then((response) => response.json())
                    .then((data) => {
                        const address = data.display_name || "Address not found.";
                        confirmAddressInput.value = address;
                    })
                    .catch((error) => {
                        console.error("Error fetching address:", error);
                        confirmAddressInput.value = "Unable to retrieve address.";
                        if (window.messageUtil) {
                            window.messageUtil.warning('Unable to retrieve address details, but location was captured.');
                        }
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
                
                if (window.messageUtil) {
                    window.messageUtil.error(errorMessage);
                }
            },
            {
                enableHighAccuracy: true,
                timeout: 10000,
                maximumAge: 0
            }
        );
    });
    
    const completeShiftForm = document.querySelector('form');
    
    // Add identifier for easier DOM targeting
    if (completeShiftForm) {
        completeShiftForm.id = 'completeShiftForm';
    }
    
    if (!completeShiftForm) {
        console.error("Could not find the shift completion form");
        return;
    }
    
    // Validate form submission
    completeShiftForm.addEventListener('submit', function(event) {
        if (signaturePad.isEmpty()) {
            event.preventDefault();
            if (window.messageUtil) {
                window.messageUtil.error('Please provide a signature before submitting.');
            } else {
                alert('Please provide a signature before submitting.');
            }
            return;
        }
        
        // Verify location data is present
        if (!latitudeField.value || !longitudeField.value) {
            event.preventDefault();
            if (window.messageUtil) {
                window.messageUtil.error('Please capture your location before submitting.');
            } else {
                alert('Please capture your location before submitting.');
            }
            return;
        }
        
        // Serialize signature for transmission
        signatureInput.value = signaturePad.toDataURL('image/png');
        console.log("Shift completion form validated successfully");
        
        if (window.messageUtil) {
            window.messageUtil.info('Processing shift completion...');
        }
    });
});
