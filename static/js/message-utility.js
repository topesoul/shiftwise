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

// Prevent duplicate initialization.
if (!window.messageUtilityInitialized) {
    document.addEventListener('DOMContentLoaded', function() {
        try {
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
