"""Panel authentication views (login / logout)."""
from django.contrib.auth import views as auth_views
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _


class PanelLoginView(auth_views.LoginView):
    template_name = "panel/login.html"
    redirect_authenticated_user = False

    def form_valid(self, form):
        user = form.get_user()
        if not (user.is_staff or user.is_superuser):
            form.add_error(None, _("This account does not have admin panel access."))
            return self.form_invalid(form)
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("panel:dashboard")


class PanelLogoutView(auth_views.LogoutView):
    next_page = reverse_lazy("panel:login")
