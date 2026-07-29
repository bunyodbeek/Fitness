"""Sinov muddati o'tmishda boshlangan profillarni tuzatadi.

`trial_started_at` dastlab `User.date_joined` dan olinardi. `User` qatori esa
profildan ancha oldin yaratilgan bo'lishi mumkin (anketani tugatmay ketgan odam
qaytib kelsa, `get_or_create(username="telegram_<id>")` eski qatorni topadi).
Shu sababli ba'zi foydalanuvchilarda sinov ro'yxatdan o'tishdan OLDIN boshlangan
va ular "7 kun bepul" xabarini allaqachon o'tib ketgan sana bilan olishgan.

Anchor profil yaratilgan paytdan oldin bo'lishi mumkin emas, shuning uchun
shunday qatorlarni `created_at` ga tekislaymiz. Boshqa hech kimga tegilmaydi —
grandfather qilingan eski foydalanuvchilarning anchor'i `created_at` dan
keyinroq turadi va shartga tushmaydi.
"""
from django.db import migrations
from django.db.models import F


def repair(apps, schema_editor):
    UserProfile = apps.get_model('apps', 'UserProfile')
    UserProfile.objects.filter(
        trial_started_at__isnull=False,
        trial_started_at__lt=F('created_at'),
    ).update(trial_started_at=F('created_at'))


class Migration(migrations.Migration):

    dependencies = [
        ('apps', '0039_userprofile_language'),
    ]

    operations = [
        migrations.RunPython(repair, migrations.RunPython.noop),
    ]
