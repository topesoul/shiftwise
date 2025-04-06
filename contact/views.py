# /workspace/shiftwise/contact/views.py

from django.conf import settings
from django.contrib import messages
from django.core.mail import send_mail
from django.shortcuts import redirect, render

from .forms import ContactForm


def contact_view(request):
    if request.method == "POST":
        form = ContactForm(request.POST)
        if form.is_valid():
            name = form.cleaned_data["name"]
            email = form.cleaned_data["email"]
            message = form.cleaned_data["message"]

            subject = f"New Contact Enquiry from {name}"
            full_message = f"Name: {name}\nEmail: {email}\n\nMessage:\n{message}"

            try:
                # Debug mode: log instead of sending actual emails
                if settings.DEBUG:
                    import logging

                    logger = logging.getLogger(__name__)
                    logger.info(f"Contact form submission (DEBUG mode): {subject}")
                    logger.info(f"From: {email}")
                    logger.info(f"Message: {message}")
                    messages.success(
                        request,
                        "Your message has been received! (In debug mode, emails are not actually sent)",
                    )
                    return redirect("contact:contact")

                # Production: send to configured admin emails
                send_mail(
                    subject,
                    full_message,
                    settings.DEFAULT_FROM_EMAIL,
                    [admin[1] for admin in settings.ADMINS],
                    fail_silently=False,
                )
                messages.success(request, "Your message has been sent successfully!")
                return redirect("contact:contact")
            except Exception as e:
                import logging

                logger = logging.getLogger(__name__)
                logger.error(f"Email sending error: {str(e)}")

                # Show detailed errors in debug, generic message in production
                if settings.DEBUG:
                    error_message = f"An error occurred while sending your message: {str(e)}"
                else:
                    error_message = (
                        "An error occurred while sending your message. Our team has been notified."
                    )

                messages.error(request, error_message)
    else:
        form = ContactForm()

    context = {"form": form}
    return render(request, "contact/contact.html", context)
