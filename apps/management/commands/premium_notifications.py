"""
Premium obuna eslatmalari.

Bu command'ni har kuni bir marta (masalan cron orqali soat 09:00 da) ishga tushirish kerak:

    python manage.py premium_notifications

Nima qiladi:
  1. Tugashiga 3 va 1 kun qolgan faol obunalar egalariga eslatma yuboradi.
  2. Muddati o'tgan, lekin hali `is_active=True` bo'lgan obunalarni deaktiv qiladi
     va foydalanuvchiga "premium tugadi" xabarini yuboradi.

Eslatma: hozircha avtomatik pul yechish (Atmos card-binding) qo'llab-quvvatlanmaydi,
shuning uchun xabarlar foydalanuvchini obunani qo'lda uzaytirishga chaqiradi.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.management.commands.bot_notisfication import send_notification
from apps.models.payments import Subscription

# Tugashidan necha kun oldin eslatma yuborish kerakligi.
REMINDER_DAYS = (3, 1)


class Command(BaseCommand):
    help = "Premium obuna tugashi haqida eslatma va tugagach xabar yuboradi."

    def handle(self, *args, **options):
        now = timezone.now()
        sent_reminders = self._send_expiry_reminders(now)
        expired = self._deactivate_expired(now)
        self.stdout.write(self.style.SUCCESS(
            f"Tayyor: {sent_reminders} ta eslatma, {expired} ta obuna deaktiv qilindi."
        ))

    def _send_expiry_reminders(self, now) -> int:
        sent = 0
        for days_left in REMINDER_DAYS:
            target_date = (now + timezone.timedelta(days=days_left)).date()
            subscriptions = Subscription.objects.filter(
                is_active=True,
                end_date__date=target_date,
            ).select_related("user")

            for sub in subscriptions:
                telegram_id = getattr(sub.user, "telegram_id", None)
                if not telegram_id:
                    continue
                message = (
                    "🔔 <b>Eslatma</b>\n\n"
                    f"Premium obunangiz tugashiga <b>{days_left} kun</b> qoldi.\n"
                    f"📅 Tugash sanasi: <b>{sub.end_date.strftime('%d.%m.%Y')}</b>\n\n"
                    "Premium funksiyalardan uzluksiz foydalanish uchun obunani uzaytiring 👇\n"
                    "/start"
                )
                if send_notification(telegram_id, message):
                    sent += 1
        return sent

    def _deactivate_expired(self, now) -> int:
        expired_subscriptions = Subscription.objects.filter(
            is_active=True,
            end_date__lt=now,
        ).select_related("user")

        count = 0
        for sub in expired_subscriptions:
            sub.is_active = False
            sub.save(update_fields=["is_active"])
            count += 1

            telegram_id = getattr(sub.user, "telegram_id", None)
            if not telegram_id:
                continue
            message = (
                "⏰ <b>Premium obuna muddati tugadi</b>\n\n"
                "Premium funksiyalar yopildi.\n\n"
                "Qayta obuna bo'lish uchun 👇\n"
                "/start"
            )
            send_notification(telegram_id, message)
        return count