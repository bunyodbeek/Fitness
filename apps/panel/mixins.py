"""Auth helpers for the custom admin panel.

The panel reuses Django's existing auth system — no new auth model or role is
introduced. Access requires an active user that is ``is_staff`` or
``is_superuser`` (the same flags Django already uses).
"""
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.urls import reverse_lazy


class StaffRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Restrict a view to authenticated staff/superusers.

    - Anonymous users are redirected to the panel login page. We use the panel
      login URL (not ``settings.LOGIN_URL``) on purpose so the Telegram login
      redirect middleware does not hijack the redirect.
    - Authenticated non-staff users get a 403 instead of a redirect loop.
    """

    login_url = reverse_lazy("panel:login")
    redirect_field_name = "next"

    def test_func(self):
        user = self.request.user
        return bool(user.is_active and (user.is_staff or user.is_superuser))

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            raise PermissionDenied
        return super().handle_no_permission()
