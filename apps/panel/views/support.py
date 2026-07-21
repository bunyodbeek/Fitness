"""Chat section — two-way support chat with users.

The list shows one row per user who has written in, newest activity first, with an
unread badge. Opening a row shows the full thread and lets staff reply; replies are
saved as ``SupportMessage(is_from_admin=True)`` and surface back in the user's Help
screen (which polls for them)."""
from django.contrib import messages as dj_messages
from django.db.models import Count, Max, Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.views.generic import DetailView

from apps.models import UserProfile
from apps.models.support import SupportMessage
from apps.panel.mixins import StaffRequiredMixin
from apps.panel.views.base import PanelContextMixin
from apps.panel.views.crud import PanelListView


class ChatListView(PanelListView):
    model = UserProfile
    nav_active = "chat"
    page_title = _("Chat")
    columns = [_("User"), _("Last message"), _("Unread"), _("Updated")]
    search_fields = ["name", "telegram_username"]
    open_url_name = "panel:chat_thread"

    def get_queryset(self):
        return (
            UserProfile.objects
            .filter(support_messages__isnull=False)
            .distinct()
            .annotate(
                last_msg_at=Max("support_messages__created_at"),
                unread=Count(
                    "support_messages",
                    filter=Q(support_messages__is_from_admin=False,
                             support_messages__is_read=False),
                ),
            )
            .order_by("-last_msg_at")
        )

    def get_row_cells(self, obj):
        last = obj.support_messages.order_by("-created_at").first()
        preview = (last.text[:60] + "…") if last and len(last.text) > 60 else (last.text if last else "—")
        if last and last.is_from_admin:
            preview = format_html('<span class="muted">{}</span> {}', _("You:"), preview)
        unread = obj.unread or 0
        unread_cell = (
            format_html('<span class="badge badge-green">{}</span>', unread)
            if unread else format_html('<span class="muted">0</span>')
        )
        return [
            obj.name or obj.telegram_username or f"#{obj.pk}",
            preview,
            unread_cell,
            obj.last_msg_at.strftime("%d.%m.%Y %H:%M") if obj.last_msg_at else "—",
        ]


class ChatThreadView(StaffRequiredMixin, PanelContextMixin, DetailView):
    model = UserProfile
    template_name = "panel/chat_thread.html"
    nav_active = "chat"
    context_object_name = "chat_user"

    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        # Mark the user's incoming messages as read once staff opens the thread.
        SupportMessage.objects.filter(
            user=self.object, is_from_admin=False, is_read=False,
        ).update(is_read=True)
        return response

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_title"] = _("Chat")
        ctx["chat_messages"] = self.object.support_messages.order_by("created_at")
        ctx["back_url"] = reverse("panel:chat")
        return ctx

    def post(self, request, *args, **kwargs):
        chat_user = get_object_or_404(UserProfile, pk=kwargs["pk"])
        text = (request.POST.get("text") or "").strip()
        if text:
            SupportMessage.objects.create(
                user=chat_user, text=text[:2000], is_from_admin=True, is_read=False,
            )
        else:
            dj_messages.error(request, _("Message cannot be empty."))
        return redirect("panel:chat_thread", pk=chat_user.pk)
