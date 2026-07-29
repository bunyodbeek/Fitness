"""
Premium obuna va bepul sinov eslatmalari.

Bu command'ni har kuni bir marta (masalan cron orqali soat 09:00 da) ishga tushirish kerak:

    python manage.py premium_notifications

Nima qiladi:
  1. BEPUL SINOV tugashiga 3, 2 va 1 (oxirgi) kun qolganlarga eslatma yuboradi.
  2. Tugashiga 3 va 1 kun qolgan faol obunalar egalariga eslatma yuboradi.
  3. Muddati o'tgan, lekin hali `is_active=True` bo'lgan obunalarni deaktiv qiladi
     va foydalanuvchiga "premium tugadi" xabarini yuboradi.

Eslatma: hozircha avtomatik pul yechish (Atmos card-binding) qo'llab-quvvatlanmaydi,
shuning uchun xabarlar foydalanuvchini obunani qo'lda uzaytirishga chaqiradi.

Xabarlar o'zbek tilida — bot xabarlari loyihada hammasi shunday. Har bir
foydalanuvchi tilida yuborish uchun tilni profilda saqlash kerak bo'ladi
(hozir u faqat cookie/sessiyada, cron'da esa so'rov konteksti yo'q).
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from apps.management.commands.bot_notisfication import send_notification
from apps.models.payments import Subscription
from apps.models.users import TRIAL_DAYS, UserProfile

# Tugashidan necha kun oldin eslatma yuborish kerakligi.
REMINDER_DAYS = (3, 1)

# Bepul sinov uchun: 3 kun, 2 kun va oxirgi kun.
TRIAL_REMINDER_DAYS = (3, 2, 1)


class Command(BaseCommand):
    help = "Bepul sinov va premium obuna tugashi haqida eslatma yuboradi."

    def handle(self, *args, **options):
        now = timezone.now()
        trial_reminders = self._send_trial_reminders(now)
        sent_reminders = self._send_expiry_reminders(now)
        expired = self._deactivate_expired(now)
        self.stdout.write(self.style.SUCCESS(
            f"Tayyor: {trial_reminders} ta sinov eslatmasi, "
            f"{sent_reminders} ta obuna eslatmasi, {expired} ta obuna deaktiv qilindi."
        ))

    # ── bepul sinov ────────────────────────────────────────────────────────
    def _send_trial_reminders(self, now) -> int:
        """Sinov tugashiga 3 / 2 / 1 kun qolganlarga xabar yuboradi.

        `trial_ends_at` — Python xossasi, uni SQL'da filtrlab bo'lmaydi, shuning
        uchun teskarisidan boramiz: qaysi kuni BOSHLANGAN sinov kerakli kuni
        tugaydi."""
        sent = 0
        for days_left in TRIAL_REMINDER_DAYS:
            ends_on = (now + timedelta(days=days_left)).date()
            started_on = ends_on - timedelta(days=TRIAL_DAYS)

            profiles = (
                UserProfile.objects
                .filter(trial_started_at__date=started_on)
                # Obuna sotib olganlarga sinov haqida yozish mantiqsiz.
                .exclude(subscription__is_active=True, subscription__end_date__gte=now)
                # Shu (yoki undan kechroq) eslatma allaqachon ketgan bo'lsa —
                # takrorlamaymiz. Cron ikki marta ishlasa ham xabar bitta bo'ladi.
                .filter(Q(trial_reminder_sent_day__isnull=True)
                        | Q(trial_reminder_sent_day__gt=days_left))
                .select_related("subscription")
            )

            for profile in profiles:
                telegram_id = getattr(profile, "telegram_id", None)
                if not telegram_id:
                    continue
                if send_notification(telegram_id, self._trial_message(profile, days_left)):
                    sent += 1
                # Yuborilmagan bo'lsa ham belgilaymiz: foydalanuvchi botni
                # bloklagan bo'lishi mumkin va har kuni qayta urinish befoyda.
                profile.trial_reminder_sent_day = days_left
                profile.save(update_fields=["trial_reminder_sent_day"])
        return sent

    @staticmethod
    def _trial_message(profile, days_left) -> str:
        ends_at = profile.trial_ends_at
        if days_left == 1:
            head = (
                "⏳ <b>Bugun — bepul sinovingizning oxirgi kuni!</b>\n\n"
                "Ertadan boshlab mashg‘ulotlar, ma’lumotnoma va barcha "
                "bo‘limlar yopiladi."
            )
        else:
            head = (
                "🔔 <b>Eslatma</b>\n\n"
                f"Bepul sinov muddatingiz tugashiga <b>{days_left} kun</b> qoldi."
            )
        return (
            f"{head}\n"
            f"📅 Tugash sanasi: <b>{ends_at.strftime('%d.%m.%Y')}</b>\n\n"
            "Mashg‘ulotlaringizni to‘xtatmaslik uchun Premium obunani "
            "rasmiylashtiring 👇\n"
            "/start"
        )

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