# /workspace/shiftwise/core/tests.py

from django.conf import settings
from django.core import mail
from django.template.loader import render_to_string
from django.test import TestCase

from .utils import send_notification_email


class EmailNotificationTests(TestCase):
    def test_send_notification_email_success(self):
        context = {
            "user": {"username": "testuser"},
            "message": "This is a test message."
        }
        
        template_content = "Hello {{ user.username }}, {{ message }}"
        
        # Create a temporary template in memory for testing
        with self.settings(TEMPLATE_DIRS=('/tmp/',)):
            with open('/tmp/test_email_template.txt', 'w') as f:
                f.write(template_content)
            
            result = send_notification_email(
                to_email="testuser@example.com",
                subject="Test Subject",
                template_path="test_email_template.txt",
                context=context
            )
            
            self.assertTrue(result)
            self.assertEqual(len(mail.outbox), 1)
            self.assertEqual(mail.outbox[0].subject, "Test Subject")
            self.assertEqual(mail.outbox[0].from_email, settings.DEFAULT_FROM_EMAIL)
            self.assertIn("testuser@example.com", mail.outbox[0].to)
            self.assertIn("Hello testuser", mail.outbox[0].body)
            self.assertIn("This is a test message", mail.outbox[0].body)

    def test_send_notification_email_failure(self):
        context = {
            "user": {"username": "testuser"},
            "message": "This is a test message."
        }
        
        # Test with invalid template path
        result = send_notification_email(
            to_email="testuser@example.com",
            subject="Test Subject",
            template_path="non_existent_template.txt",
            context=context
        )
        
        self.assertFalse(result)
        self.assertEqual(len(mail.outbox), 0)
