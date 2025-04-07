/* jshint esversion: 11 */
/**
 * Alert message management with consistent Bootstrap styling
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

        // Bootstrap alert class mapping
        this.alertClasses = {
            'success': 'alert-success',
            'info': 'alert-info',
            'warning': 'alert-warning',
            'error': 'alert-danger',
            'danger': 'alert-danger'
        };
    }

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

    displayMessage(message, type = 'info', options = {}) {
        const container = this.getContainer();
        if (!container) return null;

        const combinedOptions = { ...this.options, ...options };
        const alertClass = this.alertClasses[type] || 'alert-info';

        // Map appropriate icon for alert type
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

    dismissAlert(alertElement) {
        if (!alertElement) return;

        if (window.bootstrap && window.bootstrap.Alert) {
            const bsAlert = new window.bootstrap.Alert(alertElement);
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

    clearAllMessages() {
        const container = this.getContainer();
        if (container) {
            const alerts = container.querySelectorAll('.alert');
            alerts.forEach(alert => this.dismissAlert(alert));
        }
    }

    success(message, options = {}) {
        return this.displayMessage(message, 'success', options);
    }

    info(message, options = {}) {
        return this.displayMessage(message, 'info', options);
    }

    warning(message, options = {}) {
        return this.displayMessage(message, 'warning', options);
    }

    error(message, options = {}) {
        return this.displayMessage(message, 'error', options);
    }
}

// Global instance.
window.messageUtil = new MessageUtility();

// Legacy API for backward compatibility
window.displayMessage = (message, type) => window.messageUtil.displayMessage(message, type);

/**
 * CSRF token handling for secure XHR/fetch requests
 */
class CSRFUtility {
    constructor() {
        this.initCSRF();
    }

    /**
     * Retrieves CSRF token from available sources (cookie, form input, meta tag)
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
     * Extracts cookie value by name
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
     * Automatically adds CSRF tokens to non-safe HTTP methods
     */
    initCSRF() {
        // Integrate with jQuery AJAX if present
        if (window.jQuery) {
            window.jQuery(document).ajaxSend((e, xhr, settings) => {
                if (!/^(GET|HEAD|OPTIONS|TRACE)$/i.test(settings.type)) {
                    const token = this.getCSRFToken();
                    if (token) xhr.setRequestHeader("X-CSRFToken", token);
                }
            });
        }
        
        // Patch fetch API for automatic CSRF inclusion
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

// One-time initialization
if (!window.messageUtilityInitialized) {
    document.addEventListener('DOMContentLoaded', function() {
        try {
            window.csrfUtil = new CSRFUtility();
            
            // Remove duplicate alerts
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

            // Auto-dismiss existing alerts
            setTimeout(function() {
                const alerts = document.querySelectorAll('.alert');
                alerts.forEach(function(alert) {
                    if (alert && window.messageUtil) {
                        window.messageUtil.dismissAlert(alert);
                    }
                });
            }, 5000);
            
            // Prevent browser confirmation dialogs on links with data-no-confirm attribute
            document.addEventListener('click', function(e) {
                const target = e.target.closest('[data-no-confirm="true"]');
                if (target) {
                    // Ensure link navigates without browser confirmation
                    e.stopPropagation();
                }
            });
        } catch (e) {
            console.error('messageUtility initialization error:', e);
        }
    });

    window.messageUtilityInitialized = true;
}
