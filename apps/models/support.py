from django.db.models import CASCADE, ForeignKey
from django.db.models.fields import BooleanField, TextField
from django.utils.translation import gettext_lazy as _

from apps.models.base import CreatedBaseModel


class SupportMessage(CreatedBaseModel):
    """A single message in the two-way Help chat between a user and support.

    Messages from the user (``is_from_admin=False``) show up in the panel "Chat"
    section grouped by user; admin replies (``is_from_admin=True``) are shown back
    to the user inside the Help screen. ``is_read`` tracks whether the *other*
    side has seen the message (used for unread badges)."""

    user = ForeignKey('apps.UserProfile', CASCADE, related_name='support_messages',
                      verbose_name=_("Foydalanuvchi"))
    text = TextField(_("Xabar"))
    is_from_admin = BooleanField(_("Admindan"), default=False)
    is_read = BooleanField(_("O'qilgan"), default=False)

    class Meta:
        verbose_name = _("Chat xabari")
        verbose_name_plural = _("Chat")
        ordering = ['created_at']

    def __str__(self):
        who = "admin" if self.is_from_admin else "user"
        return f"[{who}] {self.user_id}: {self.text[:40]}"
