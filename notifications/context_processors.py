# /workspace/shiftwise/notifications/context_processors.py

from django.db.models import Count
from .models import Notification


def notifications_processor(request):
    """
    Context processor to make notifications available to all templates.
    
    Adds:
    - notifications: List of 5 most recent notifications
    - unread_notifications_count: Count of unread notifications
    """
    context = {
        'notifications': [],
        'unread_notifications_count': 0
    }
    
    if request.user.is_authenticated:
        # Get the 5 most recent notifications
        notifications = (
            Notification.objects
            .filter(user=request.user)
            .order_by('-created_at')[:5]
        )
        
        # Count unread notifications
        unread_count = (
            Notification.objects
            .filter(user=request.user, read=False)
            .count()
        )
        
        context['notifications'] = notifications
        context['unread_notifications_count'] = unread_count
    
    return context