// /workspace/shiftwise/static/js/shift_complete.js

document.addEventListener('DOMContentLoaded', function() {
    // Signature pad setup
    const canvas = document.getElementById('signaturePad');
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
    document.querySelector('.clearSignature').addEventListener('click', function() {
        signaturePad.clear();
    });
    
    // Get location
    document.querySelector('.getLocation').addEventListener('click', function() {
        const locationStatus = document.getElementById('locationStatus');
        const latitudeField = document.getElementById('id_shift_completion_latitude');
        const longitudeField = document.getElementById('id_shift_completion_longitude');
        const addressField = document.getElementById('id_confirm_address');
        
        locationStatus.innerHTML = '<span class="text-info">Getting location...</span>';
        
        if (navigator.geolocation) {
            navigator.geolocation.getCurrentPosition(
                function(position) {
                    const latitude = position.coords.latitude;
                    const longitude = position.coords.longitude;
                    
                    latitudeField.value = latitude;
                    longitudeField.value = longitude;
                    
                    // Fetch approximate address
                    fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${latitude}&lon=${longitude}`)
                        .then(response => response.json())
                        .then(data => {
                            if (data && data.display_name) {
                                addressField.value = data.display_name;
                            } else {
                                addressField.value = `Latitude: ${latitude}, Longitude: ${longitude}`;
                            }
                        })
                        .catch(error => {
                            addressField.value = `Latitude: ${latitude}, Longitude: ${longitude}`;
                            console.error('Error fetching address:', error);
                        });
                    
                    locationStatus.innerHTML = '<span class="text-success">Location captured successfully!</span>';
                },
                function(error) {
                    let errorMessage = 'Unknown error.';
                    switch(error.code) {
                        case error.PERMISSION_DENIED:
                            errorMessage = 'Location permission denied.';
                            break;
                        case error.POSITION_UNAVAILABLE:
                            errorMessage = 'Location information unavailable.';
                            break;
                        case error.TIMEOUT:
                            errorMessage = 'Location request timed out.';
                            break;
                    }
                    locationStatus.innerHTML = `<span class="text-danger">${errorMessage}</span>`;
                }
            );
        } else {
            locationStatus.innerHTML = '<span class="text-danger">Geolocation not supported by this browser.</span>';
        }
    });
    
    // Capture signature on submit
    document.querySelector('form').addEventListener('submit', function(event) {
        if (signaturePad.isEmpty()) {
            event.preventDefault();
            alert('Provide a signature before submitting.');
            return;
        }
        
        const signatureData = signaturePad.toDataURL();
        document.querySelector('.signatureInput').value = signatureData;
        
        const latitudeField = document.getElementById('id_shift_completion_latitude');
        const longitudeField = document.getElementById('id_shift_completion_longitude');
        if (!latitudeField.value || !longitudeField.value) {
            event.preventDefault();
            alert('Capture your location before submitting.');
        }
    });
});
