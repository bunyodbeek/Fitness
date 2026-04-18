import os

import django
from apps.bot.utils import setup_webhook
from root.settings import BOT_TOKEN, WEBAPP_URL

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "root.settings")
django.setup()

setup_webhook(BOT_TOKEN, WEBAPP_URL)
