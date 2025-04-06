/**
 * Utility for managing alert messages with consistent styling.
 */
class MessageUtility {
    constructor(options = {}) {
        this.options = {
            containerSelector: '#message-container',
            defaultDuration: 5000,
            animationDuration: 150,
            autoCreate: true,
            ...options
        };

        // Map of alert types to Bootstrap classes.
        this.alertClasses = {
            'success': 'alert-success',
            'info': 'alert-info',
            'warning': 'alert-warning',
            'error': 'alert-danger',
            'danger': 'alert-danger'
        };
    }

    // Returns or creates the message container.
    getContainer() {
        let container = document.querySelector(this.options.containerSelector);

        if (!container && this.options.autoCreate) {
            const mainContainer = document.querySelector('main.container');
            if (mainContainer) {
                container = document.createElement('div');
                container.id = this.options.containerSelector.replace('#', '');
                container.className = 'message-container';
                mainContainer.insertBefore(container, mainContainer.firstChild);
            }
        }

        return container;
    }

    // Creates and displays an alert message.
    displayMessage(message, type = 'info', options = {}) {
        const container = this.getContainer();
        if (!container) return null;

        const combinedOptions = { ...this.options, ...options };
        const alertClass = this.alertClasses[type] || 'alert-info';

        // Map icon based on alert type
        let icon = '';
        if (type === 'success') {
            icon = '<i class="fas fa-check-circle mr-2"></i>';
        } else if (type === 'info') {
            icon = '<i class="fas fa-info-circle mr-2"></i>';
        } else if (type === 'warning') {
            icon = '<i class="fas fa-exclamation-triangle mr-2"></i>';
        } else if (type === 'error' || type === 'danger') {
            icon = '<i class="fas fa-times-circle mr-2"></i>';
        }

        const alertElement = document.createElement('div');
        alertElement.className = `alert ${alertClass} alert-dismissible fade show`;
        alertElement.setAttribute('role', 'alert');
        alertElement.setAttribute('aria-live', 'polite');
        alertElement.innerHTML = `
            ${icon}${message}
            <button type="button" class="close" data-dismiss="alert" aria-label="Close">
                <span aria-hidden="true">&times;</span>
            </button>
        `;

        container.appendChild(alertElement);

        if (combinedOptions.defaultDuration > 0) {
            setTimeout(() => this.dismissAlert(alertElement), combinedOptions.defaultDuration);
        }

        return alertElement;
    }

    // Dismisses the specified alert element.
    dismissAlert(alertElement) {
        if (!alertElement) return;

        if (window.bootstrap && bootstrap.Alert) {
            const bsAlert = new bootstrap.Alert(alertElement);
            bsAlert.close();
        } else {
            alertElement.classList.remove('show');
            alertElement.classList.add('fade');

            setTimeout(() => {
                if (alertElement.parentNode) {
                    alertElement.parentNode.removeChild(alertElement);
                }
            }, this.options.animationDuration);
        }
    }

    // Clears all alert messages.
    clearAllMessages() {
        const container = this.getContainer();
        if (container) {
            const alerts = container.querySelectorAll('.alert');
            alerts.forEach(alert => this.dismissAlert(alert));
        }
    }

    // Shorthand for displaying a success message.
    success(message, options = {}) {
        return this.displayMessage(message, 'success', options);
    }

    // Shorthand for displaying an info message.
    info(message, options = {}) {
        return this.displayMessage(message, 'info', options);
    }

    // Shorthand for displaying a warning message.
    warning(message, options = {}) {
        return this.displayMessage(message, 'warning', options);
    }

    // Shorthand for displaying an error message.
    error(message, options = {}) {
        return this.displayMessage(message, 'error', options);
    }
}

// Global instance.
window.messageUtil = new MessageUtility();

// Expose legacy API.
window.displayMessage = (message, type) => window.messageUtil.displayMessage(message, type);
/**
 * CSRF token management for securing XHR/fetch requests
 */
class CSRFUtility {
    constructor() {
        this.initCSRF();
    }

    /**
     * Retrieves CSRF token from cookie, form input, or meta tag
     */
    getCSRFToken() {
        const token = this.getCookie('csrftoken');
        if (token) return token;
        
        const csrfInput = document.querySelector('input[name="csrfmiddlewaretoken"]');
        if (csrfInput) return csrfInput.value;
        
        const metaTag = document.querySelector('meta[name="csrf-token"]');
        if (metaTag) return metaTag.getAttribute('content');
        
        return null;
    }
    
    /**
     * Parses document cookies to find specified value
     */
    getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }
    
    /**
     * Injects CSRF tokens into non-safe HTTP methods
     */
    initCSRF() {
        // Add CSRF headers to jQuery AJAX requests
        if (window.jQuery) {
            jQuery(document).ajaxSend((e, xhr, settings) => {
                if (!/^(GET|HEAD|OPTIONS|TRACE)$/i.test(settings.type)) {
                    const token = this.getCSRFToken();
                    if (token) xhr.setRequestHeader("X-CSRFToken", token);
                }
            });
        }
        
        // Intercept fetch API to add CSRF headers
        const originalFetch = window.fetch;
        window.fetch = (url, options = {}) => {
            if (options.method && 
                !/^(GET|HEAD|OPTIONS|TRACE)$/i.test(options.method) && 
                (url.toString().startsWith(window.location.origin) || url.toString().startsWith('/'))) {
                
                options.headers = options.headers || {};
                
                if (!options.headers['X-CSRFToken'] && !options.headers['x-csrftoken']) {
                    const token = this.getCSRFToken();
                    if (token) options.headers['X-CSRFToken'] = token;
                }
            }
            return originalFetch(url, options);
        };
    }
}

// Prevent duplicate initialization.
if (!window.messageUtilityInitialized) {
    document.addEventListener('DOMContentLoaded', function() {
        try {
            // Initialize CSRF protection
            window.csrfUtil = new CSRFUtility();
            
            // Handle duplicate alerts
            const seenMessages = new Set();
            const alerts = document.querySelectorAll('.alert');

            alerts.forEach(function(alert) {
                if (!alert || !alert.parentNode) return;

                const message = alert.textContent.trim();
                if (seenMessages.has(message)) {
                    alert.parentNode.removeChild(alert);
                } else {
                    seenMessages.add(message);
                }
            });

            // Auto-dismiss alerts.
            setTimeout(function() {
                const alerts = document.querySelectorAll('.alert');
                alerts.forEach(function(alert) {
                    if (alert && window.messageUtil) {
                        window.messageUtil.dismissAlert(alert);
                    }
                });
            }, 5000);
        } catch (e) {
            console.error('messageUtility initialization error:', e);
        }
    });

    window.messageUtilityInitialized = true;
}
