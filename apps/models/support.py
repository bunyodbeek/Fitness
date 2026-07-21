from django.core.exceptions import ValidationError
from django.db.models import CASCADE, ForeignKey
from django.db.models.fields import BooleanField, TextField
from django.db.models.fields.files import ImageField
from django.utils.translation import gettext_lazy as _

from apps.models.base import CreatedBaseModel


class SupportMessage(CreatedBaseModel):
    """A single message in the two-way Help chat between a user and support.

    Messages from the user (``is_from_admin=False``) show up in the panel "Chat"
    section grouped by user; admin replies (``is_from_admin=True``) are shown back
    to the user inside the Help screen. ``is_read`` tracks whether the *other*
    side has seen the message (used for unread badges).

    A message carries text, an image, or both — but never neither (enforced by
    ``clean()`` and by the send views)."""

    user = ForeignKey('apps.UserProfile', CASCADE, related_name='support_messages',
                      verbose_name=_("Foydalanuvchi"))
    text = TextField(_("Xabar"), blank=True, default='')
    image = ImageField(_("Rasm"), upload_to='support/images/', null=True, blank=True)
    thumbnail = ImageField(_("Nusxa"), upload_to='support/thumbnails/', null=True, blank=True)
    is_from_admin = BooleanField(_("Admindan"), default=False)
    is_read = BooleanField(_("O'qilgan"), default=False)

    class Meta:
        verbose_name = _("Chat xabari")
        verbose_name_plural = _("Chat")
        ordering = ['created_at']

    def clean(self):
        if not (self.text or '').strip() and not self.image:
            raise ValidationError(_("A message must have text or an image."))

    def __str__(self):
        who = "admin" if self.is_from_admin else "user"
        preview = self.text[:40] if self.text else "[image]"
        return f"[{who}] {self.user_id}: {preview}"
