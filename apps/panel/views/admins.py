"""Admins section — manage staff/superuser accounts (existing auth, no new role)."""
from django.contrib import messages
from django.db.models import Q
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from apps.models import User
from apps.panel.forms import AdminUserForm
from apps.panel.views.crud import PanelCreateView, PanelDeleteView, PanelListView, PanelUpdateView


def _yesno(flag):
    if flag:
        return format_html('<span class="badge badge-green">{}</span>', _("Yes"))
    return format_html('<span class="badge badge-free">{}</span>', _("No"))


class AdminListView(PanelListView):
    model = User
    nav_active = "admins"
    page_title = _("Admins")
    columns = [_("Username"), _("Email"), _("Role"), _("Staff"), _("Superuser")]
    search_fields = ["username", "email"]
    create_url_name = "panel:admin_add"
    edit_url_name = "panel:admin_edit"
    delete_url_name = "panel:admin_delete"
    create_label = _("Add admin")
    queryset = User.objects.filter(Q(is_staff=True) | Q(is_superuser=True)).order_by("username")

    def get_row_cells(self, obj):
        return [
            obj.username,
            obj.email or "—",
            obj.get_role_display(),
            _yesno(obj.is_staff),
            _yesno(obj.is_superuser),
        ]


class AdminCreateView(PanelCreateView):
    model = User
    form_class = AdminUserForm
    nav_active = "admins"
    page_title = _("Add admin")
    success_url = reverse_lazy("panel:admins")
    success_message = _("Admin created.")

    def get_initial(self):
        initial = super().get_initial()
        initial.setdefault("is_staff", True)
        return initial


class AdminUpdateView(PanelUpdateView):
    model = User
    form_class = AdminUserForm
    nav_active = "admins"
    page_title = _("Edit admin")
    success_url = reverse_lazy("panel:admins")


class AdminDeleteView(PanelDeleteView):
    model = User
    nav_active = "admins"
    page_title = _("Delete admin")
    success_url = reverse_lazy("panel:admins")

    def form_valid(self, form):
        if self.object == self.request.user:
            messages.error(self.request, _("You cannot delete your own account."))
            return redirect(self.success_url)
        return super().form_valid(form)
