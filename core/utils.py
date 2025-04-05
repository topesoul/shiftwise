# /workspace/shiftwise/core/utils.py

import logging
import random
import secrets
import string
from django.http import JsonResponse
from django.contrib.auth.models import Group
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings

logger = logging.getLogger(__name__)

def assign_user_to_group(user, group_name):
    """
    Assigns a user to a specific Django group, creating it if it doesn't exist.
    
    Args:
        user: User model instance
        group_name: String name of the group
    
    Returns:
        bool: Success status of the operation
    """
    try:
        group, created = Group.objects.get_or_create(name=group_name)
        user.groups.add(group)
        logger.info(f"User {user.username} assigned to group {group_name}")
        return True
    except Exception as e:
        logger.error(f"Error assigning user {user.username} to group {group_name}: {e}")
        return False


def generate_unique_code(prefix="", length=8):
    """
    Generates a unique alphanumeric code with optional prefix.
    
    Args:
        prefix: String prefix to add to the generated code
        length: Length of the random portion of the code
    
    Returns:
        str: Generated unique code
    """
    chars = string.ascii_uppercase + string.digits
    random_part = ''.join(random.choice(chars) for _ in range(length))
    return f"{prefix}{random_part}"


def generate_random_password(length=12):
    """
    Generates a secure random password of specified length.
    
    Args:
        length: Length of the generated password
    
    Returns:
        str: Secure random password
    """
    alphabet = string.ascii_letters + string.digits + string.punctuation
    while True:
        password = ''.join(secrets.choice(alphabet) for _ in range(length))
        if (any(c.islower() for c in password)
                and any(c.isupper() for c in password)
                and any(c.isdigit() for c in password)
                and any(c in string.punctuation for c in password)):
            return password


def ajax_response_with_message(success, message, data=None):
    """
    Creates a standardized JSON response for AJAX requests.
    
    Args:
        success (bool): Whether the operation was successful
        message (str): Message to display to the user
        data (dict, optional): Additional data to return
        
    Returns:
        JsonResponse: A standardized JSON response
    """
    response_data = {
        'success': success,
        'message': message
    }
    
    if data:
        response_data.update(data)
        
    return JsonResponse(response_data)


def send_notification_email(to_email, subject, template_path, context):
    """
    Sends an email notification using a template.
    
    Args:
        to_email (str or list): Recipient email(s)
        subject (str): Email subject
        template_path (str): Path to the email template
        context (dict): Template context variables
    
    Returns:
        bool: Whether the email was sent successfully
    """
    try:
        message = render_to_string(template_path, context)
        recipient_list = [to_email] if isinstance(to_email, str) else to_email
        
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipient_list,
            fail_silently=False
        )
        logger.info(f"Email sent to {recipient_list} with subject: {subject}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {e}")
        return False