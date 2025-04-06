// workspaces/static/js/messages.js

document.addEventListener('DOMContentLoaded', function() {
    // Auto-dismiss messages after 5 seconds
    setTimeout(function() {
        const alerts = document.querySelectorAll('.alert');
        alerts.forEach(function(alert) {
            if (window.bootstrap && window.bootstrap.Alert) {
                const bsAlert = new window.bootstrap.Alert(alert);
                bsAlert.close();
            } else {
                // Fallback if bootstrap JavaScript isn't loaded
                alert.classList.remove('show');
                alert.classList.add('fade');
                setTimeout(function() {
                    alert.remove();
                }, 150);
            }
        });
    }, 5000);
    
    // For AJAX operations, add message display function
    window.displayMessage = function(message, messageType) {
        let messageContainer = document.getElementById('message-container');
        if (!messageContainer) {
            // Create container if it doesn't exist
            const mainContainer = document.querySelector('main.container');
            if (!mainContainer) return;
            
            const newContainer = document.createElement('div');
            newContainer.id = 'message-container';
            newContainer.className = 'message-container';
            
            mainContainer.insertBefore(newContainer, mainContainer.firstChild);
            messageContainer = newContainer;
        }
        
        const alertClass = {
            'success': 'alert-success',
            'info': 'alert-info',
            'warning': 'alert-warning',
            'error': 'alert-danger'
        }[messageType] || 'alert-info';
        
        const alertHTML = `
            <div class="alert ${alertClass} alert-dismissible fade show" role="alert">
                ${message}
                <button type="button" class="close" data-dismiss="alert" aria-label="Close">
                    <span aria-hidden="true">&times;</span>
                </button>
            </div>
        `;
        
        messageContainer.innerHTML += alertHTML;
        
        // Auto-dismiss after 5 seconds
        setTimeout(function() {
            const newAlert = messageContainer.querySelector('.alert:last-child');
            if (newAlert) {
                if (window.bootstrap && window.bootstrap.Alert) {
                    const bsAlert = new window.bootstrap.Alert(newAlert);
                    bsAlert.close();
                } else {
                    // Fallback if bootstrap JavaScript isn't loaded
                    newAlert.classList.remove('show');
                    newAlert.classList.add('fade');
                    setTimeout(function() {
                        newAlert.remove();
                    }, 150);
                }
            }
        }, 5000);
    };
});
