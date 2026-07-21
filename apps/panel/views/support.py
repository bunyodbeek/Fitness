"""Chat section — two-way support chat with users.

The list shows one row per user who has written in, newest activity first, with an
unread badge. Opening a row shows the full thread and lets staff reply; replies are
saved as ``SupportMessage(is_from_admin=True)`` and surface back in the user's Help
screen (which polls for them)."""
from datetime import timedelta

from django.contrib import messages as dj_messages
from django.db.models import Count, Max, Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.views.generic import DetailView

from apps.models import UserProfile
from apps.models.support import SupportMessage
from apps.panel.mixins import StaffRequiredMixin
from apps.panel.views.base import PanelContextMixin
from apps.panel.views.crud import PanelListView

# Messages from the same sender within this gap are grouped into one visual block.
GROUP_GAP_SECONDS = 5 * 60


def build_thread_rows(messages):
    """Turn a time-ordered iterable of ``SupportMessage`` into render rows:

    a list mixing date-separator chips and message rows. Each message is annotated
    (in-memory, not saved) with ``time_label``, ``group_start`` and ``group_end`` so
    the template can group consecutive same-sender bubbles and show a timestamp only
    on the last of each group. Reused by the admin thread and the user Help screen."""
    msgs = list(messages)
    today = timezone.localdate()
    yesterday = today - timedelta(days=1)
    rows = []

    for i, m in enumerate(msgs):
        local_dt = timezone.localtime(m.created_at)
        day = local_dt.date()
        prev = msgs[i - 1] if i > 0 else None
        nxt = msgs[i + 1] if i + 1 < len(msgs) else None

        prev_day = timezone.localtime(prev.created_at).date() if prev else None
        new_day = prev_day != day

        if new_day:
            rows.append({
                'sep': True,
                'label_key': 'today' if day == today else 'yesterday' if day == yesterday else '',
                'label_date': local_dt.strftime('%d.%m.%Y'),
            })

        if new_day or prev is None:
            group_start = True
        else:
            gap = (local_dt - timezone.localtime(prev.created_at)).total_seconds()
            group_start = prev.is_from_admin != m.is_from_admin or gap > GROUP_GAP_SECONDS

        if nxt is None:
            group_end = True
        else:
            nxt_local = timezone.localtime(nxt.created_at)
            if nxt_local.date() != day:
                group_end = True
            else:
                gap = (nxt_local - local_dt).total_seconds()
                group_end = nxt.is_from_admin != m.is_from_admin or gap > GROUP_GAP_SECONDS

        m.time_label = local_dt.strftime('%H:%M')
        m.group_start = group_start
        m.group_end = group_end
        rows.append({'sep': False, 'msg': m})

    return rows


class ChatListView(PanelListView):
    model = UserProfile
    nav_active = "chat"
    page_title = _("Chat")
    columns = [_("User"), _("Last message"), _("Unread"), _("Updated")]
    search_fields = ["name"]
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
            obj.name or (f"#{obj.telegram_id}" if obj.telegram_id else f"#{obj.pk}"),
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
        ctx["thread_rows"] = build_thread_rows(
            self.object.support_messages.order_by("created_at")
        )
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
