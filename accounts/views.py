# /workspace/shiftwise/accounts/views.py

import base64
import logging
from io import BytesIO

import pyotp
import qrcode

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import (
    authenticate,
    get_backends,
    get_user_model,
    login,
    logout,
)
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import Group
from django.contrib.messages.views import SuccessMessageMixin
from django.core.mail import send_mail
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.generic import (
    CreateView,
    DeleteView,
    FormView,
    ListView,
    TemplateView,
    UpdateView,
    View,
)

from core.mixins import (
    AgencyManagerRequiredMixin,
    AgencyOwnerRequiredMixin,
    AgencyStaffRequiredMixin,
    SubscriptionRequiredMixin,
    SuperuserRequiredMixin,
)
from shifts.models import ShiftAssignment
from shiftwise.utils import get_address_from_address_line1

from .forms import (
    AcceptInvitationForm,
    AgencyForm,
    AgencySignUpForm,
    InvitationForm,
    MFAForm,
    ProfilePictureForm,
    SignUpForm,
    UpdateProfileForm,
    UserForm,
    UserUpdateForm,
)
from .models import Agency, Invitation, Profile

User = get_user_model()
logger = logging.getLogger(__name__)


class CustomLoginView(FormView):
    """Handles authentication with optional MFA flow redirection."""

    template_name = "accounts/login.html"
    form_class = AuthenticationForm
    success_url = reverse_lazy("accounts:mfa_verify")

    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return self.redirect_user(request.user)
        return super().get(request, *args, **kwargs)

    def form_valid(self, form):
        username = form.cleaned_data.get("username")
        password = form.cleaned_data.get("password")
        user = authenticate(username=username, password=password)
        if user:
            backend = self.get_user_backend(user)
            if (
                hasattr(user.profile, "totp_secret")
                and user.profile.totp_secret
            ):
                self.request.session["pre_mfa_user_id"] = user.id
                self.request.session["auth_backend"] = backend
                logger.info(
                    f"User {user.username} needs MFA verification."
                )
                return redirect("accounts:mfa_verify")
            else:
                login(self.request, user, backend=backend)
                messages.success(
                    self.request, f"Welcome back, {user.get_full_name()}!"
                )
                logger.info(f"User {user.username} logged in without MFA.")
                return self.redirect_user(user)
        else:
            # Non-field error for authentication failure
            form.add_error(None, "Invalid username or password.")
            logger.warning(f"Failed login attempt for username: {username}")
            return self.form_invalid(form)

    def form_invalid(self, form):
        # Let Django's built-in form validation handle field errors
        logger.warning(f"Failed login: {self.request.POST.get('username')}")
        return super().form_invalid(form)

    def redirect_user(self, user):
        if user.is_superuser:
            return redirect("accounts:superuser_dashboard")
        elif user.groups.filter(name="Agency Managers").exists():
            return redirect("accounts:agency_dashboard")
        elif user.groups.filter(name="Agency Staff").exists():
            return redirect("accounts:staff_dashboard")
        else:
            return redirect("home:home")

    def get_user_backend(self, user):
        backends = get_backends()
        for backend in backends:
            if hasattr(backend, "get_user") and backend.get_user(user.pk):
                return f"{backend.__module__}.{backend.__class__.__name__}"
        return "django.contrib.auth.backends.ModelBackend"


class LogoutView(LoginRequiredMixin, View):
    """Processes user logout and session termination."""

    def get(self, request, *args, **kwargs):
        logger.info(f"User {request.user.username} logged out.")
        logout(request)
        messages.success(request, "You have successfully logged out.")
        return redirect(reverse("home:home"))


class MFAVerifyView(FormView):
    """Validates TOTP codes during two-factor authentication."""

    template_name = "accounts/mfa_verify.html"
    form_class = MFAForm
    success_url = reverse_lazy("home:home")

    def dispatch(self, request, *args, **kwargs):
        if (
            "pre_mfa_user_id" not in request.session
            or "auth_backend" not in request.session
        ):
            messages.error(
                request, "Session expired or invalid. Please log in again."
            )
            logger.warning(
                "MFA verification attempted without a valid session."
            )
            return redirect("accounts:login_view")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        totp_code = form.cleaned_data.get("totp_code")
        user_id = self.request.session.get("pre_mfa_user_id")
        backend = self.request.session.get("auth_backend")
        user = get_object_or_404(User, id=user_id)
        totp = pyotp.TOTP(user.profile.totp_secret)
        # Allow for time skew by checking current and adjacent windows
        if totp.verify(totp_code, valid_window=1):
            login(self.request, user, backend=backend)
            messages.success(
                self.request, f"Welcome back, {user.get_full_name()}!"
            )
            logger.info(f"User {user.username} logged in with MFA.")
            del self.request.session["pre_mfa_user_id"]
            del self.request.session["auth_backend"]
            return self.redirect_user(user)
        else:
            # Field-level validation for MFA code
            form.add_error("totp_code", "Invalid MFA code. Please try again.")
            logger.warning(
                f"Invalid MFA code entered by user {user.username}."
            )
            return self.form_invalid(form)

    def redirect_user(self, user):
        if user.is_superuser:
            return redirect("accounts:superuser_dashboard")
        elif user.groups.filter(name="Agency Managers").exists():
            return redirect("accounts:agency_dashboard")
        elif user.groups.filter(name="Agency Staff").exists():
            return redirect("accounts:staff_dashboard")
        else:
            return redirect("home:home")


class SignUpView(FormView):
    """Processes new user registration."""

    template_name = "accounts/signup.html"
    form_class = SignUpForm
    success_url = reverse_lazy("accounts:login_view")

    def form_valid(self, form):
        user = form.save()
        messages.success(
            self.request, "Your account has been created successfully."
        )
        logger.info(f"New user {user.username} signed up.")
        return super().form_valid(form)


class SignupSelectionView(TemplateView):
    """Displays account type selection page."""

    template_name = "accounts/signup_selection.html"


class AgencySignUpView(CreateView):
    """Registers new agencies with agency owner privileges."""

    model = User
    form_class = AgencySignUpForm
    template_name = "accounts/agency_signup.html"
    success_url = reverse_lazy("accounts:profile")

    def form_valid(self, form):
        user = form.save()
        username = user.username
        password = form.cleaned_data.get("password1")
        user = authenticate(username=username, password=password)
        if user is not None:
            agency_owners_group, _ = Group.objects.get_or_create(
                name="Agency Owners"
            )
            user.groups.add(agency_owners_group)
            logger.info(
                f"User {user.username} assigned to 'Agency Owners' group."
            )
            backend = self.get_user_backend(user)
            login(self.request, user, backend=backend)
            messages.success(
                self.request, "Your agency account has been created."
            )
            logger.info(f"Agency account created for user {user.username}.")
            return redirect("accounts:profile")
        else:
            messages.error(
                self.request, "Authentication failed. Please try again."
            )
            logger.error(
                f"Authentication failed for user {username} during signup."
            )
            return self.form_invalid(form)

    def get_user_backend(self, user):
        backends = get_backends()
        for backend in backends:
            if hasattr(backend, "get_user") and backend.get_user(user.pk):
                return f"{backend.__module__}.{backend.__class__.__name__}"
        return "django.contrib.auth.backends.ModelBackend"


class ActivateTOTPView(LoginRequiredMixin, View):
    """Sets up time-based MFA and generates QR code for authenticator apps."""

    def get(self, request, *args, **kwargs):
        if request.user.profile.totp_secret:
            messages.info(request, "MFA is already enabled on your account.")
            return redirect("accounts:profile")
        totp_secret = pyotp.random_base32()
        request.session["totp_secret"] = totp_secret

        totp = pyotp.TOTP(totp_secret, interval=settings.MFA_TOTP_PERIOD)
        provisioning_uri = totp.provisioning_uri(
            name=request.user.email, issuer_name=settings.MFA_TOTP_ISSUER
        )

        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(provisioning_uri)
        qr.make(fit=True)

        img = qr.make_image(fill="black", back_color="white")
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        qr_code_image = base64.b64encode(buffer.getvalue()).decode()

        context = {"qr_code_image": qr_code_image, "totp_secret": totp_secret}
        return render(request, "accounts/activate_totp.html", context)

    def post(self, request, *args, **kwargs):
        code = request.POST.get("totp_code")
        totp_secret = request.session.get("totp_secret")
        if not totp_secret:
            messages.error(
                request, "Session expired. Please try activating MFA again."
            )
            logger.warning(
                f"User {request.user.username} MFA activation missing session."
            )
            return redirect("accounts:activate_totp")
        totp = pyotp.TOTP(totp_secret, interval=settings.MFA_TOTP_PERIOD)
        if totp.verify(code, valid_window=1):
            request.user.profile.totp_secret = totp_secret
            request.user.profile.save()
            recovery_codes = request.user.profile.generate_recovery_codes()
            messages.success(
                request,
                "MFA activated. Please save your recovery codes securely.",
            )
            logger.info(f"MFA activated for user {request.user.username}.")
            del request.session["totp_secret"]
            context = {"recovery_codes": recovery_codes}
            return render(request, "accounts/recovery_codes.html", context)
        else:
            messages.error(request, "Invalid code. Please try again.")
            logger.warning(
                f"Invalid MFA code entered by user {request.user.username}."
            )
            totp = pyotp.TOTP(totp_secret, interval=settings.MFA_TOTP_PERIOD)
            provisioning_uri = totp.provisioning_uri(
                name=request.user.email, issuer_name=settings.MFA_TOTP_ISSUER
            )
            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(provisioning_uri)
            qr.make(fit=True)
            img = qr.make_image(fill="black", back_color="white")
            buffer = BytesIO()
            img.save(buffer, format="PNG")
            qr_code_image = base64.b64encode(buffer.getvalue()).decode()
            context = {
                "qr_code_image": qr_code_image,
                "totp_secret": totp_secret,
            }
            return render(request, "accounts/activate_totp.html", context)


class DisableTOTPView(LoginRequiredMixin, View):
    """Removes time-based MFA from user account."""

    def get(self, request, *args, **kwargs):
        return render(request, "accounts/deactivate_totp.html")

    def post(self, request, *args, **kwargs):
        request.user.profile.totp_secret = None
        request.user.profile.save()
        messages.success(request, "MFA has been disabled.")
        logger.info(f"MFA disabled for user {request.user.username}.")
        return redirect("accounts:profile")


class ResendTOTPCodeView(LoginRequiredMixin, View):
    """Regenerates TOTP QR code for authentication setup."""

    def get(self, request, *args, **kwargs):
        user_totp_secret = (
            request.user.profile.totp_secret or pyotp.random_base32()
        )
        totp = pyotp.TOTP(user_totp_secret, interval=settings.MFA_TOTP_PERIOD)
        provisioning_uri = totp.provisioning_uri(
            name=request.user.email, issuer_name=settings.MFA_TOTP_ISSUER
        )
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(provisioning_uri)
        qr.make(fit=True)
        img = qr.make_image(fill="black", back_color="white")
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        qr_code_image = base64.b64encode(buffer.getvalue()).decode()
        if not request.user.profile.totp_secret:
            request.user.profile.totp_secret = user_totp_secret
            request.user.profile.save()
        context = {
            "qr_code_image": qr_code_image,
            "totp_secret": user_totp_secret,
        }
        return render(request, "accounts/reauthenticate.html", context)


class ProfileView(LoginRequiredMixin, View):
    """Displays and processes user profile updates."""

    template_name = "accounts/profile.html"

    def get(self, request, *args, **kwargs):
        profile = Profile.objects.get(user=request.user)
        profile_form = UpdateProfileForm(instance=profile)
        picture_form = ProfilePictureForm(instance=profile)
        context = self.get_context_data(
            profile=profile,
            profile_form=profile_form,
            picture_form=picture_form,
        )
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        profile, _ = Profile.objects.get_or_create(user=request.user)
        profile_form = UpdateProfileForm(request.POST, instance=profile)
        picture_form = ProfilePictureForm(
            request.POST, request.FILES, instance=profile
        )
        if profile_form.is_valid() and picture_form.is_valid():
            try:
                with transaction.atomic():
                    profile_form.save()
                    if "profile_picture" in request.FILES:
                        picture_form.save()
                    elif "profile_picture-clear" in request.POST:
                        profile.profile_picture = None
                        profile.save(update_fields=["profile_picture"])
                messages.success(
                    request, "Your profile has been updated successfully."
                )
                logger.info(
                    f"Profile updated for user {request.user.username}"
                )
                return redirect("accounts:profile")
            except Exception as e:
                logger.error(
                    f"Error updating profile for user {request.user.username}: {e}"
                )
                messages.error(
                    request,
                    "An error occurred while updating your profile. Please try again.",
                )
        else:
            if profile_form.errors:
                logger.warning(f"Form errors: {profile_form.errors}")
            if picture_form.errors:
                logger.warning(f"Picture form errors: {picture_form.errors}")
        messages.error(request, "Please correct the errors below.")
        context = self.get_context_data(
            profile_form=profile_form,
            picture_form=picture_form,
            open_modal=True,
        )
        return render(request, self.template_name, context)

    def get_context_data(self, **kwargs):
        context = {}
        user = self.request.user
        assigned_shifts = ShiftAssignment.objects.filter(worker=user)
        today = timezone.now().date()
        upcoming_shifts = (
            assigned_shifts.filter(shift__shift_date__gte=today)
            .select_related("shift")
            .order_by("shift__shift_date")
        )
        past_shifts = (
            assigned_shifts.filter(shift__shift_date__lt=today)
            .select_related("shift")
            .order_by("-shift__shift_date")
        )
        if hasattr(user, "profile") and user.profile.agency:
            context["agency"] = user.profile.agency
        if hasattr(user, "owned_agency") and user.owned_agency:
            context["owned_agency"] = user.owned_agency
        context.update(
            {
                "upcoming_shifts": upcoming_shifts,
                "past_shifts": past_shifts,
                "GOOGLE_PLACES_API_KEY": settings.GOOGLE_PLACES_API_KEY,
                "is_agency_owner": (
                    user.groups.filter(name="Agency Owners").exists()
                ),
                "is_agency_manager": (
                    user.groups.filter(name="Agency Managers").exists()
                ),
            }
        )
        context.update(kwargs)
        return context


class AgencyDashboardView(
    LoginRequiredMixin,
    AgencyManagerRequiredMixin,
    SubscriptionRequiredMixin,
    View,
):
    """Provides agency management interface for authorized users."""

    def get(self, request, *args, **kwargs):
        user = request.user
        if user.is_superuser:
            agencies = Agency.objects.all()
            shifts = ShiftAssignment.objects.filter(
                shift__agency__in=agencies
            ).select_related("shift", "worker")
            return render(
                request,
                "accounts/agency_dashboard.html",
                {"agencies": agencies, "shifts": shifts},
            )
        else:
            agency = user.profile.agency
            shifts = ShiftAssignment.objects.filter(
                shift__agency=agency
            ).select_related("shift", "worker")
            return render(
                request,
                "accounts/agency_dashboard.html",
                {"agency": agency, "shifts": shifts},
            )


class StaffDashboardView(
    LoginRequiredMixin,
    AgencyStaffRequiredMixin,
    SubscriptionRequiredMixin,
    View,
):
    """Displays shift assignments and relevant information for staff members."""

    def get(self, request, *args, **kwargs):
        user = request.user
        today = timezone.now().date()
        assignments = ShiftAssignment.objects.filter(
            worker=user
        ).select_related("shift")
        assigned_shift_ids = assignments.values_list("shift_id", flat=True)
        upcoming_shifts = assignments.filter(shift__shift_date__gte=today)
        past_shifts = assignments.filter(shift__shift_date__lt=today)
        return render(
            request,
            "accounts/staff_dashboard.html",
            {
                "user": user,
                "upcoming_shifts": upcoming_shifts,
                "past_shifts": past_shifts,
                "assigned_shift_ids": list(assigned_shift_ids),
            },
        )


class SuperuserDashboardView(LoginRequiredMixin, SuperuserRequiredMixin, View):
    """Provides system-wide administration interface for superusers."""

    def get(self, request, *args, **kwargs):
        agencies = Agency.objects.all()
        users = User.objects.all()
        context = {"agencies": agencies, "users": users}
        return render(request, "accounts/superuser_dashboard.html", context)


class InviteStaffView(
    LoginRequiredMixin,
    AgencyManagerRequiredMixin,
    SubscriptionRequiredMixin,
    FormView,
):
    """Manages sending and tracking staff invitations."""

    template_name = "accounts/invite_staff.html"
    form_class = InvitationForm
    success_url = reverse_lazy("shifts:staff_list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update({"user": self.request.user})
        return kwargs

    def form_valid(self, form):
        invitation = form.save(commit=False)
        invitation.invited_by = self.request.user
        if not self.request.user.is_superuser:
            if (
                hasattr(self.request.user, "profile")
                and self.request.user.profile.agency
            ):
                invitation.agency = self.request.user.profile.agency
                logger.debug(
                    f"Agency assigned to invitation: {invitation.agency.name}"
                )
            else:
                messages.error(
                    self.request, "You are not associated with any agency."
                )
                logger.error(
                    f"User {self.request.user.id} invite failed - no agency."
                )
                return redirect("accounts:profile")
        else:
            invitation.agency = form.cleaned_data.get("agency")
            if invitation.agency:
                logger.debug(
                    f"Agency {invitation.agency.name} by user {self.request.user.id}"
                )
            else:
                logger.debug(
                    "Superuser is inviting staff without associating to an agency."
                )
        invitation.save()
        logger.info(
            f"Invitation: {invitation.email} by user {self.request.user.id}"
        )
        invite_link = self.request.build_absolute_uri(
            reverse(
                "accounts:accept_invitation",
                kwargs={"token": invitation.token},
            )
        )
        agency_name = (
            invitation.agency.name if invitation.agency else "ShiftWise"
        )
        context = {"agency_name": agency_name, "invite_link": invite_link}
        subject = "ShiftWise Staff Invitation"
        message = render_to_string(
            "accounts/emails/invite_staff_email.txt", context
        )
        try:
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [invitation.email],
                fail_silently=False,
            )
            messages.success(
                self.request, f"Invitation sent to {invitation.email}."
            )
            logger.info(
                f"Invitation email sent to {invitation.email} by {self.request.user.username}"
            )
        except Exception as e:
            messages.error(
                self.request,
                "Failed to send invitation email. Please try again later.",
            )
            logger.exception(
                f"Failed to send invitation email to {invitation.email}: {e}"
            )
            invitation.delete()
            logger.debug(
                f"Invitation deleted due to email sending failure: {invitation.email}"
            )
            return redirect("shifts:staff_list")
        return super().form_valid(form)


class AcceptInvitationView(View):
    """Processes staff invitation acceptances and account creation."""

    def dispatch(self, request, *args, **kwargs):
        """
        Override dispatch to handle exceptions gracefully
        """
        try:
            return super().dispatch(request, *args, **kwargs)
        except Exception as e:
            logger.exception(f"Error in AcceptInvitationView: {e}")
            messages.error(
                request,
                "An error occurred while processing your invitation. Please contact support."
            )
            return redirect("home:home")

    def get(self, request, token, *args, **kwargs):
        try:
            # Validate token format before querying database
            try:
                uuid_token = uuid.UUID(str(token))
            except ValueError:
                messages.error(request, "Invalid invitation token format.")
                logger.warning(f"Invalid invitation token format: {token}")
                return redirect("accounts:login_view")

            # Find the invitation
            invitation = get_object_or_404(Invitation, token=uuid_token, is_active=True)
            
            if invitation.is_expired():
                messages.error(request, "This invitation has expired.")
                logger.warning(f"Expired invitation accessed: {invitation.email}")
                return redirect("accounts:login_view")
                
            form = AcceptInvitationForm(initial={"email": invitation.email})
            return render(
                request, "accounts/accept_invitation.html", {"form": form}
            )
        except Exception as e:
            logger.exception(f"Error in invitation get view: {e}")
            messages.error(
                request, 
                "An error occurred while loading the invitation. Please contact support."
            )
            return redirect("home:home")

    def post(self, request, token, *args, **kwargs):
        try:
            # Validate token format before querying database
            try:
                uuid_token = uuid.UUID(str(token))
            except ValueError:
                messages.error(request, "Invalid invitation token format.")
                logger.warning(f"Invalid invitation token format in post: {token}")
                return redirect("accounts:login_view")
                
            # Find the invitation
            invitation = get_object_or_404(Invitation, token=uuid_token, is_active=True)
            
            if invitation.is_expired():
                messages.error(request, "This invitation has expired.")
                logger.warning(
                    f"Expired invitation attempted to accept: {invitation.email}"
                )
                return redirect("accounts:login_view")
                
            form = AcceptInvitationForm(
                request.POST,
                initial={"email": invitation.email},
                invitation=invitation,
                request=request,
            )
            
            if form.is_valid():
                try:
                    with transaction.atomic():
                        # Create user in a transaction to ensure all related operations succeed
                        user = form.save(commit=False)
                        user.save()
                        
                        # Ensure profile exists
                        profile, created = Profile.objects.get_or_create(user=user)
                        
                        # Add to Agency Staff group
                        agency_staff_group, _ = Group.objects.get_or_create(
                            name="Agency Staff"
                        )
                        user.groups.add(agency_staff_group)
                        logger.info(
                            f"User {user.username} assigned to 'Agency Staff' group."
                        )
                        
                        # Link to agency if available
                        if invitation.agency:
                            profile.agency = invitation.agency
                            profile.save()
                            logger.debug(
                                f"User {user.username} linked to agency {invitation.agency.name}."
                            )
                        else:
                            logger.debug(f"User {user.username} not linked to any agency.")
                            
                        # Mark invitation as accepted
                        invitation.is_active = False
                        invitation.accepted_at = timezone.now()
                        invitation.save()
                        logger.info(
                            f"Invitation {invitation.email} marked as accepted by {user.username}."
                        )
                        
                        # Login the user
                        backend = self.get_user_backend(user)
                        login(request, user, backend=backend)
                        messages.success(
                            request, "Your account has been created successfully."
                        )
                        logger.info(
                            f"User {user.username} logged in after accepting invitation."
                        )
                        
                        return redirect("accounts:staff_dashboard")
                except Exception as e:
                    logger.exception(f"Transaction error in AcceptInvitationView: {e}")
                    messages.error(
                        request, 
                        "An error occurred while creating your account. Please contact support."
                    )
                    return redirect("home:home")
            else:
                if form.errors:
                    logger.warning(f"Accept invitation form errors: {form.errors}")
                messages.error(request, "Please correct the errors below.")
                logger.warning(
                    f"Invalid acceptance form submitted by {invitation.email}"
                )
                return render(
                    request, "accounts/accept_invitation.html", {"form": form}
                )
        except Exception as e:
            logger.exception(f"Error in invitation post view: {e}")
            messages.error(
                request, 
                "An error occurred while processing your invitation. Please contact support."
            )
            return redirect("home:home")

    def get_user_backend(self, user):
        backends = get_backends()
        for backend in backends:
            if hasattr(backend, "get_user") and backend.get_user(user.pk):
                return f"{backend.__module__}.{backend.__class__.__name__}"
        return "django.contrib.auth.backends.ModelBackend"


@login_required
def get_address(request):
    address_line1 = request.GET.get("address_line1")
    if not address_line1:
        return JsonResponse(
            {"success": False, "message": "No address provided."}
        )
    addresses = get_address_from_address_line1(address_line1)
    if addresses:
        return JsonResponse({"success": True, "addresses": addresses})
    else:
        return JsonResponse(
            {
                "success": False,
                "message": "No addresses found for the provided address.",
            }
        )


class AgencyListView(
    LoginRequiredMixin,
    AgencyOwnerRequiredMixin,
    SubscriptionRequiredMixin,
    ListView,
):
    """Lists agencies with access control based on user role."""

    model = Agency
    template_name = "accounts/manage_agencies.html"
    context_object_name = "agencies"

    def get_queryset(self):
        if self.request.user.is_superuser:
            return Agency.objects.all()
        else:
            return Agency.objects.filter(
                id=self.request.user.profile.agency.id
            )


class AgencyCreateView(
    LoginRequiredMixin,
    SuperuserRequiredMixin,
    SubscriptionRequiredMixin,
    SuccessMessageMixin,
    CreateView,
):
    """Handles agency creation for superusers."""

    model = Agency
    form_class = AgencyForm
    template_name = "accounts/agency_form.html"
    success_url = reverse_lazy("accounts:manage_agencies")
    success_message = "Agency has been created successfully."

    def form_valid(self, form):
        response = super().form_valid(form)
        user = self.request.user
        profile = user.profile
        profile.agency = form.instance
        profile.save()
        logger.info(
            f"Agency '{form.instance.name}' created and linked to user {user.username}."
        )
        return response


class AgencyUpdateView(
    LoginRequiredMixin,
    AgencyOwnerRequiredMixin,
    SubscriptionRequiredMixin,
    SuccessMessageMixin,
    UpdateView,
):
    """Manages agency detail modifications."""

    model = Agency
    form_class = AgencyForm
    template_name = "accounts/agency_form.html"
    success_url = reverse_lazy("accounts:manage_agencies")
    success_message = "Agency has been updated successfully."

    def get_queryset(self):
        if self.request.user.is_superuser:
            return Agency.objects.all()
        else:
            return Agency.objects.filter(
                id=self.request.user.profile.agency.id
            )

    def form_valid(self, form):
        response = super().form_valid(form)
        logger.info(
            f"Agency '{form.instance.name}' updated by user {self.request.user.username}."
        )
        return response


class AgencyDeleteView(
    LoginRequiredMixin,
    SuperuserRequiredMixin,
    SubscriptionRequiredMixin,
    SuccessMessageMixin,
    DeleteView,
):
    """Removes agencies from the system (superusers only)."""

    model = Agency
    template_name = "accounts/agency_confirm_delete.html"
    success_url = reverse_lazy("accounts:manage_agencies")
    success_message = "Agency has been deleted successfully."

    def delete(self, request, *args, **kwargs):
        agency = self.get_object()
        response = super().delete(request, *args, **kwargs)
        logger.info(
            f"Agency '{agency.name}' deleted by user {request.user.username}."
        )
        return response


class UserListView(
    LoginRequiredMixin,
    AgencyManagerRequiredMixin,
    SubscriptionRequiredMixin,
    ListView,
):
    """Displays users with appropriate access controls."""

    model = User
    template_name = "accounts/manage_users.html"
    context_object_name = "users"

    def get_queryset(self):
        if self.request.user.is_superuser:
            return User.objects.all()
        else:
            return User.objects.filter(
                profile__agency=self.request.user.profile.agency
            )


class UserCreateView(
    LoginRequiredMixin,
    AgencyManagerRequiredMixin,
    SubscriptionRequiredMixin,
    SuccessMessageMixin,
    CreateView,
):
    """Provides user creation interface for managers."""

    model = User
    form_class = UserForm
    template_name = "accounts/user_form.html"
    success_url = reverse_lazy("accounts:manage_users")
    success_message = "User has been created successfully."

    def get_form_kwargs(self):
        return super().get_form_kwargs()

    def form_valid(self, form):
        user = form.save()
        group = form.cleaned_data.get("group")
        if group:
            user.groups.add(group)
            logger.info(
                f"User '{user.username}' added to group '{group.name}'."
            )
        logger.info(
            f"User '{user.username}' created by {self.request.user.username}."
        )
        return super().form_valid(form)


class UserUpdateView(
    LoginRequiredMixin,
    AgencyManagerRequiredMixin,
    SubscriptionRequiredMixin,
    SuccessMessageMixin,
    UpdateView,
):
    """Manages user profile modifications by managers."""

    model = User
    form_class = UserUpdateForm
    template_name = "accounts/user_form.html"
    success_url = reverse_lazy("accounts:manage_users")
    success_message = "User has been updated successfully."

    def get_queryset(self):
        if self.request.user.is_superuser:
            return User.objects.all()
        else:
            return User.objects.filter(
                profile__agency=self.request.user.profile.agency
            )
            
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # For agency owners, limit group choices to Agency Staff and Agency Managers
        if not self.request.user.is_superuser and self.request.user.groups.filter(name="Agency Owners").exists():
            form.fields['group'].queryset = Group.objects.filter(name__in=["Agency Staff", "Agency Managers"])
        return form

    def form_valid(self, form):
        user = form.save()
        group = form.cleaned_data.get("group")
        if group:
            user.groups.clear()
            user.groups.add(group)
            logger.info(
                f"User '{user.username}' updated and assigned to group '{group.name}'."
            )
        return super().form_valid(form)


class UserDeleteView(
    LoginRequiredMixin,
    AgencyManagerRequiredMixin,
    SubscriptionRequiredMixin,
    SuccessMessageMixin,
    DeleteView,
):
    """Handles user deactivation rather than deletion."""

    model = User
    template_name = "accounts/user_confirm_delete.html"
    success_url = reverse_lazy("accounts:manage_users")
    success_message = "User has been deactivated successfully."

    def get_queryset(self):
        if self.request.user.is_superuser:
            return User.objects.all()
        else:
            return User.objects.filter(
                profile__agency=self.request.user.profile.agency
            )

    def dispatch(self, request, *args, **kwargs):
        user = self.request.user
        if not user.is_superuser:
            target_user = self.get_object()
            if (
                not hasattr(target_user, "profile")
                or not hasattr(user, "profile")
                or target_user.profile.agency != user.profile.agency
            ):
                messages.error(
                    request,
                    "You do not have permission to deactivate this user.",
                )
                return redirect(self.success_url)
        return super().dispatch(request, *args, **kwargs)

    def delete(self, request, *args, **kwargs):
        user = self.get_object()
        user.is_active = False
        user.save()
        self.success_message = (
            f'User "{user.username}" has been deactivated successfully.'
        )
        messages.success(request, self.success_message)
        logger.info(
            f"User '{user.username}' deactivated by user {request.user.username}."
        )
        return redirect(self.success_url)
