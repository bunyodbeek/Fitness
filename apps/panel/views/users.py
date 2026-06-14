"""Users section — CRUD over UserProfile (the app's domain user)."""
import uuid

from django.urls import reverse_lazy
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from apps.models import User, UserProfile
from apps.panel.forms import UserProfileForm
from apps.panel.views.crud import PanelCreateView, PanelDeleteView, PanelListView, PanelUpdateView


def _status_badge(profile):
    if profile.is_premium:
        return format_html('<span class="badge badge-premium">{}</span>', _("Premium"))
    return format_html('<span class="badge badge-free">{}</span>', _("Free"))


class UserListView(PanelListView):
    model = UserProfile
    nav_active = "users"
    page_title = _("Users")
    columns = [_("Name"), _("Telegram ID"), _("Goal"), _("Joined"), _("Status")]
    search_fields = ["name", "telegram_id"]
    create_url_name = "panel:user_add"
    edit_url_name = "panel:user_edit"
    delete_url_name = "panel:user_delete"
    create_label = _("Add user")

    def get_queryset(self):
        return super().get_queryset().select_related("user").order_by("-created_at")

    def get_row_cells(self, obj):
        return [
            obj.name,
            obj.telegram_id or "—",
            obj.get_fitness_goal_display() or "—",
            obj.created_at.strftime("%d.%m.%Y"),
            _status_badge(obj),
        ]


class UserCreateView(PanelCreateView):
    model = UserProfile
    form_class = UserProfileForm
    nav_active = "users"
    page_title = _("Add user")
    success_url = reverse_lazy("panel:users")
    success_message = _("User created.")

    def form_valid(self, form):
        # A UserProfile needs a backing auth User (OneToOne). Create one.
        username = f"user_{uuid.uuid4().hex[:10]}"
        user = User.objects.create_user(username=username)
        form.instance.user = user
        return super().form_valid(form)


class UserUpdateView(PanelUpdateView):
    model = UserProfile
    form_class = UserProfileForm
    nav_active = "users"
    page_title = _("Edit user")
    success_url = reverse_lazy("panel:users")


class UserDeleteView(PanelDeleteView):
    model = UserProfile
    nav_active = "users"
    page_title = _("Delete user")
    success_url = reverse_lazy("panel:users")
