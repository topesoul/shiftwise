# /workspace/shiftwise/contact/forms.py

from django import forms
from django.core.validators import EmailValidator, MinLengthValidator
from django.utils.html import strip_tags


class ContactForm(forms.Form):
    name = forms.CharField(
        max_length=100,
        label="Your Name",
        widget=forms.TextInput(attrs={"class": "form-control"}),
        validators=[MinLengthValidator(2, "Name must be at least 2 characters")],
    )
    email = forms.EmailField(
        label="Your Email",
        widget=forms.EmailInput(attrs={"class": "form-control"}),
        validators=[EmailValidator(message="Enter a valid email address")],
    )
    message = forms.CharField(
        label="Your Message",
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 5}),
        validators=[MinLengthValidator(10, "Message must be at least 10 characters")],
    )

    # Hidden field used for spam detection
    honeypot = forms.CharField(
        required=False,
        widget=forms.HiddenInput(),
        label="Leave empty",
    )

    def clean_honeypot(self):
        """Check that honeypot field is empty."""
        value = self.cleaned_data["honeypot"]
        if value:
            raise forms.ValidationError("Spam check failed.")
        return value

    def clean_name(self):
        """Sanitize name field."""
        name = self.cleaned_data.get("name", "")
        return strip_tags(name)

    def clean_message(self):
        """Sanitize message field."""
        message = self.cleaned_data.get("message", "")
        return strip_tags(message)
