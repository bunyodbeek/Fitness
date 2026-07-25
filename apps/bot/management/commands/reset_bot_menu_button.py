"""Xabar maydoni yonidagi global Web App menyu tugmasini olib tashlaydi.

BotFather'da sozlangan menu button ("Fitness") qat'iy URL'ga bog'langan: til
prefiksi hech qachon yangilanmaydi, shuning uchun foydalanuvchi ilovada tilni
o'zgartirgandan keyin ham eski tildagi sahifa ochiladi; bundan tashqari u alohida
webview sessiyasini ochib, cookie'lari yo'qolgan holatda form-POST'larni buzadi.

`/start` har bir chat uchun bu tugmani allaqachon olib tashlaydi
(`apps.bot.bot_view._use_commands_menu`), bu buyruq esa GLOBAL (default) qiymatni
tozalaydi — ya'ni boshqa `/start` bosmagan foydalanuvchilarda ham yo'qoladi.

Serverda bir marta ishga tushiring:

    python manage.py reset_bot_menu_button
"""

from django.core.management.base import BaseCommand, CommandError
from telebot.types import MenuButtonCommands

from apps.bot.bot import bot
from root.settings import BOT_TOKEN


class Command(BaseCommand):
    help = "Clear the bot's global Web App menu button (show the commands menu instead)."

    def handle(self, *args, **options):
        if not BOT_TOKEN:
            raise CommandError("BOT_TOKEN (or TELEGRAM_BOT_TOKEN) is not configured.")

        # chat_id BERILMAYDI -> default (barcha chatlar uchun) menyu tugmasi.
        if not bot.set_chat_menu_button(menu_button=MenuButtonCommands()):
            raise CommandError("Telegram setChatMenuButton failed.")

        self.stdout.write(self.style.SUCCESS(
            "Menu button tozalandi — Mini App faqat reply keyboard orqali ochiladi."
        ))
