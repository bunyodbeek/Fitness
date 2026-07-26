"""Bot menu button'ini (xabar maydoni yonidagi tugma) Mini App'ga sozlaydi.

`/start` har bir chat uchun buni allaqachon qiladi
(:func:`apps.bot.bot_view._set_menu_button`), bu buyruq esa GLOBAL (default)
qiymatni o'rnatadi — ya'ni hech qachon `/start` bosmagan foydalanuvchilarda ham
tugma to'g'ri URL bilan ko'rinadi. BotFather orqali qo'lda kiritilgan, til prefiksi
qotib qolgan eski URL'ni ham shu buyruq bosib o'tadi.

Serverda bir marta ishga tushiring (va URL o'zgarsa qayta):

    python manage.py set_bot_menu_button

Chat ro'yxatidagi ko'k **OPEN** tugmasi esa Bot API orqali sozlanmaydi — u
BotFather'dagi "Main Mini App" sozlamasi (README/qo'llanmaga qarang), URL sifatida
xuddi shu manzilni bering:

    python manage.py set_bot_menu_button --show-url
"""

from django.core.management.base import BaseCommand, CommandError
from telebot.types import MenuButtonWebApp, WebAppInfo

from apps.bot.bot import bot
from apps.bot.bot_view import MENU_BUTTON_TEXT, miniapp_url
from root.settings import BOT_TOKEN


class Command(BaseCommand):
    help = "Set the bot's global Web App menu button to the language-neutral /app/ entry."

    def add_arguments(self, parser):
        parser.add_argument(
            "--text",
            dest="text",
            default=MENU_BUTTON_TEXT,
            help=f"Menu button label (default: {MENU_BUTTON_TEXT!r}).",
        )
        parser.add_argument(
            "--show-url",
            action="store_true",
            dest="show_url",
            help="Only print the Mini App URL (BotFather 'Main Mini App' uchun).",
        )

    def handle(self, *args, **options):
        url = miniapp_url()

        if options["show_url"]:
            self.stdout.write(url)
            return

        if not BOT_TOKEN:
            raise CommandError("BOT_TOKEN (or TELEGRAM_BOT_TOKEN) is not configured.")

        # chat_id BERILMAYDI -> default (barcha chatlar uchun) menyu tugmasi.
        ok = bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(
                type="web_app", text=options["text"], web_app=WebAppInfo(url=url)
            )
        )
        if not ok:
            raise CommandError("Telegram setChatMenuButton failed.")

        self.stdout.write(self.style.SUCCESS(f"Menu button: {options['text']!r} -> {url}"))
        self.stdout.write(
            "Chat ro'yxatidagi OPEN tugmasi uchun BotFather -> Bot Settings -> "
            f"Configure Mini App -> Enable Mini App -> {url}"
        )
