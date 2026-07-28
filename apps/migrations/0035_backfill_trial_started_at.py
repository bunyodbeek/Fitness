"""Mavjud foydalanuvchilarga bepul sinov muddatini QAYTA beradi.

Paywall gate joriy qilinayotgan paytda bazadagi HAMMA foydalanuvchi allaqachon
ro'yxatdan o'tganiga 7 kundan ko'p bo'lgan. Agar anchor `date_joined` dan
olinsa, deploy qilingan daqiqada obunasi yo'q barcha foydalanuvchilar hech
qanday ogohlantirishsiz premium sahifasiga qamalib qolardi.

Shuning uchun ular uchun anchor DEPLOY VAQTIGA qo'yiladi — eski foydalanuvchi
ham xuddi yangisi kabi to'liq 7 kun oladi. Bu bir martalik "grandfathering":
migratsiya faqat `trial_started_at IS NULL` bo'lgan qatorlarga tegadi, shuning
uchun qayta ishga tushirilsa hech kimga ikkinchi marta sinov bermaydi.

Yangi foydalanuvchilar bu yerga tushmaydi — ular uchun anchor
`UserProfile.save()` da `user.date_joined` dan yoziladi.
"""
from django.db import migrations
from django.utils import timezone


def grandfather_existing_users(apps, schema_editor):
    UserProfile = apps.get_model('apps', 'UserProfile')
    UserProfile.objects.filter(trial_started_at__isnull=True).update(
        trial_started_at=timezone.now(),
    )


def noop_reverse(apps, schema_editor):
    """Ortga qaytarish anchor'ni tozalaydi — maydonning o'zi 0034 da o'chadi."""
    UserProfile = apps.get_model('apps', 'UserProfile')
    UserProfile.objects.update(trial_started_at=None)


class Migration(migrations.Migration):

    dependencies = [
        ('apps', '0034_userprofile_trial_started_at'),
    ]

    operations = [
        migrations.RunPython(grandfather_existing_users, noop_reverse),
    ]
