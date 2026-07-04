from django.conf import settings
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView as DjangoLoginView
from django.contrib.auth.views import LogoutView as DjangoLogoutView
from django.contrib.auth.views import (
    PasswordChangeDoneView as DjangoPasswordChangeDoneView,
)
from django.contrib.auth.views import PasswordChangeView as DjangoPasswordChangeView
from django.contrib.auth.views import (
    PasswordResetCompleteView as DjangoPasswordResetCompleteView,
)
from django.contrib.auth.views import (
    PasswordResetConfirmView as DjangoPasswordResetConfirmView,
)
from django.contrib.auth.views import (
    PasswordResetDoneView as DjangoPasswordResetDoneView,
)
from django.contrib.auth.views import PasswordResetView as DjangoPasswordResetView
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, ListView, TemplateView, UpdateView

from origami_common.audit import audit_logger
from origami_common.decorators import rate_limit
from origami_common.helpers import _json_error, _parse_json_body, _permission_denied
from origami_common.mixins import ActivePageMixin

from .forms import ProfileEditForm, RegistrationForm
from .mixins import AdminOrDMRequiredMixin


def password_reset_enabled() -> bool:
    """Whether the email-based password-reset chain is switched on.

    Reset emails only work when the consuming project has real outbound email
    configured (``EMAIL_BACKEND``/SMTP settings), so the whole chain is opt-in:
    set ``ORIGAMI_AUTH_ENABLE_PASSWORD_RESET = True`` alongside the email
    settings. Off by default so projects without SMTP never render a reset
    link that leads nowhere.
    """
    return bool(getattr(settings, "ORIGAMI_AUTH_ENABLE_PASSWORD_RESET", False))


class RegisterView(ActivePageMixin, CreateView):
    """Create an account and sign the new user straight in."""

    form_class = RegistrationForm
    template_name = "origami_auth/register.html"
    active_page = "register"

    def get_success_url(self):
        # A subclass that sets an explicit success_url wins; otherwise, since
        # registering signs you in, go wherever login goes.
        if self.success_url:
            return str(self.success_url)
        return settings.LOGIN_REDIRECT_URL or reverse_lazy("origami_auth:profile")

    def form_valid(self, form):
        response = super().form_valid(form)
        login(self.request, self.object)
        return response


@method_decorator(rate_limit("login", max_requests=10, window_seconds=300), name="post")
class LoginView(ActivePageMixin, DjangoLoginView):
    template_name = "origami_auth/login.html"
    redirect_authenticated_user = True
    active_page = "login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # The "Forgot your password?" link only renders when the reset chain
        # is actually wired up (see password_reset_enabled).
        context["password_reset_enabled"] = password_reset_enabled()
        return context


class LogoutView(DjangoLogoutView):
    """Logs out and redirects to ``settings.LOGOUT_REDIRECT_URL``.

    Consuming apps that want a specific landing page can subclass and set
    ``next_page``.
    """


class ProfileView(LoginRequiredMixin, TemplateView):
    template_name = "origami_auth/profile.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user_id = self.kwargs.get("user_id")
        if user_id and self.request.user.can_manage_users:
            context["profile_user"] = get_object_or_404(get_user_model(), pk=user_id)
            context["active_page"] = None  # Viewing another user's profile
        else:
            context["profile_user"] = self.request.user
            context["active_page"] = "profile"
        context["can_edit_roles"] = self.request.user.is_role_admin
        return context


class ProfileEditView(LoginRequiredMixin, ActivePageMixin, UpdateView):
    """Standard form-based editing of the signed-in user's own profile."""

    form_class = ProfileEditForm
    template_name = "origami_auth/profile_edit.html"
    success_url = reverse_lazy("origami_auth:profile")
    active_page = "profile"

    def get_object(self, queryset=None):
        # Always the signed-in user; editing other users stays admin-only via
        # the existing profile_update_field endpoint.
        return self.request.user


@method_decorator(
    rate_limit("password_change", max_requests=10, window_seconds=300), name="post"
)
class PasswordChangeView(ActivePageMixin, DjangoPasswordChangeView):
    """Logged-in password change (Django's built-in view, app templates)."""

    template_name = "origami_auth/password_change.html"
    success_url = reverse_lazy("origami_auth:password_change_done")
    active_page = "profile"


class PasswordChangeDoneView(ActivePageMixin, DjangoPasswordChangeDoneView):
    template_name = "origami_auth/password_change_done.html"
    active_page = "profile"


@method_decorator(
    rate_limit("password_reset", max_requests=5, window_seconds=300), name="post"
)
class PasswordResetView(DjangoPasswordResetView):
    """Start of the email reset chain — only routed when opted in (see urls.py)."""

    template_name = "origami_auth/password_reset.html"
    email_template_name = "origami_auth/password_reset_email.txt"
    subject_template_name = "origami_auth/password_reset_subject.txt"
    success_url = reverse_lazy("origami_auth:password_reset_done")


class PasswordResetDoneView(DjangoPasswordResetDoneView):
    template_name = "origami_auth/password_reset_done.html"


class PasswordResetConfirmView(DjangoPasswordResetConfirmView):
    template_name = "origami_auth/password_reset_confirm.html"
    success_url = reverse_lazy("origami_auth:password_reset_complete")


class PasswordResetCompleteView(DjangoPasswordResetCompleteView):
    template_name = "origami_auth/password_reset_complete.html"


class UsersListView(
    ActivePageMixin, LoginRequiredMixin, AdminOrDMRequiredMixin, ListView
):
    model = get_user_model()
    template_name = "origami_auth/users_list.html"
    context_object_name = "users"
    active_page = "users"
    paginate_by = 50
    ordering = ["username"]


PROFILE_FIELDS = {"real_name", "email", "phone", "discord", "preferred_contact"}
ROLE_FIELDS = {"is_role_admin", "is_dm", "is_player"}


@login_required
@require_POST
@rate_limit("profile_update", max_requests=30, window_seconds=60)
def profile_update_field(request, user_id=None):
    """Update a single profile field via AJAX."""
    data, err = _parse_json_body(request)
    if err:
        return err
    field = data.get("field")  # type: ignore[union-attr]
    value = data.get("value")  # type: ignore[union-attr]

    user_model = get_user_model()

    # Determine target user - check permission before database lookup
    if user_id:
        if not request.user.can_manage_users:
            return _permission_denied()
        # Use permission denied for non-existent users to prevent enumeration
        try:
            target_user = user_model.objects.get(pk=user_id)
        except user_model.DoesNotExist:
            return _permission_denied()
    else:
        target_user = request.user

    if field in ROLE_FIELDS:
        if not request.user.is_role_admin:
            return _permission_denied()
        new_value = value in (True, "true", "on", 1)
        old_value = getattr(target_user, field)
        setattr(target_user, field, new_value)
        # Audit log role changes
        if user_id and old_value != new_value:
            audit_logger.info(
                "ROLE_CHANGE: user=%s changed field=%s from %s to %s on user=%s (pk=%s)",
                request.user.username,
                field,
                old_value,
                new_value,
                target_user.username,
                target_user.pk,
            )
    elif field in PROFILE_FIELDS:
        old_value = getattr(target_user, field)
        setattr(target_user, field, value)
        # Enforce the field's validators (phone/discord regex, email format).
        # save() alone never runs them, and this AJAX endpoint is the only write
        # path for these fields.
        try:
            target_user._meta.get_field(field).clean(value, target_user)
        except ValidationError as err:
            return _json_error(err.messages[0])
        # Audit log profile changes by admin
        if user_id and old_value != value:
            audit_logger.info(
                "PROFILE_CHANGE: user=%s changed field=%s on user=%s (pk=%s)",
                request.user.username,
                field,
                target_user.username,
                target_user.pk,
            )
    else:
        return _json_error("Invalid field")

    target_user.save()
    return JsonResponse({"success": True})


@login_required
@require_POST
@rate_limit("delete_user", max_requests=10, window_seconds=60)
def delete_user(request, user_id):
    """Delete a user (admin/DM only)."""
    # Check permission before database lookup to prevent user ID enumeration
    if not request.user.can_manage_users:
        return _permission_denied()

    user = get_object_or_404(get_user_model(), pk=user_id)

    # Prevent self-deletion
    if user.pk == request.user.pk:
        return _json_error("Cannot delete yourself")

    audit_logger.info(
        "USER_DELETE: user=%s deleted user=%s (pk=%s)",
        request.user.username,
        user.username,
        user.pk,
    )
    user.delete()
    return JsonResponse({"success": True})
