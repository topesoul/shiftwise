// /workspace/shiftwise/static/js/notification.js

document.addEventListener('DOMContentLoaded', function() {
    // Handle notifications in the dropdown
    document.querySelectorAll('.notification-item').forEach(function(item) {
        item.addEventListener('click', function(event) {
            const notificationId = this.dataset.notificationId;
            
            // If this is an unread notification, mark it as read
            if (this.classList.contains('unread')) {
                markNotificationAsRead(notificationId);
                this.classList.remove('unread', 'font-weight-bold');
                
                // Update the notification counter
                const counter = document.querySelector('#notificationsDropdown .badge');
                if (counter) {
                    const count = parseInt(counter.textContent, 10);
                    if (count > 1) {
                        counter.textContent = count - 1;
                    } else {
                        counter.remove();
                    }
                }
            }
            
            // If notification has a URL, allow the link to proceed
            if (this.getAttribute('href') !== '#') {
                return true;
            }
            
            // Otherwise prevent default behavior
            event.preventDefault();
        });
    });
    
    // Handle mark read buttons on notification list page
    document.querySelectorAll('.mark-read-btn').forEach(button => {
        button.addEventListener('click', function() {
            const notificationId = this.getAttribute('data-id');
            markNotificationAsRead(notificationId);
            
            // Update UI to show notification is read
            this.closest('.notification-item').classList.remove('unread', 'font-weight-bold');
            this.parentElement.style.textDecoration = "line-through";
            this.remove();
        });
    });
    
    // Helper function to mark a notification as read via AJAX
    function markNotificationAsRead(notificationId) {
        // Get CSRF token from cookie
        const csrftoken = getCookie('csrftoken');
        
        fetch(`/notifications/mark-read/${notificationId}/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': csrftoken,
                'Content-Type': 'application/json'
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                console.log('Notification marked as read:', notificationId);
            }
        })
        .catch(error => {
            console.error('Error marking notification as read:', error);
        });
    }
    
    // Function to get CSRF token from cookies
    function getCookie(name) {
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
});
