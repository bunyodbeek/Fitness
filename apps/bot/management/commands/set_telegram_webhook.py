from django.core.management.base import BaseCommand, CommandError

from apps.bot.utils import setup_webhook
from root.settings import BOT_TOKEN, TELEGRAM_WEBHOOK_URL


class Command(BaseCommand):
    help = "Set Telegram webhook for the configured bot token."

    def add_arguments(self, parser):
        parser.add_argument(
            "--domain",
            dest="domain",
            default=TELEGRAM_WEBHOOK_URL,
            help="Public base domain, e.g. https://shredzville.com",
        )

    def handle(self, *args, **options):
        token = BOT_TOKEN
        domain = (options.get("domain") or "").strip()

        if not token:
            raise CommandError("BOT_TOKEN (or TELEGRAM_BOT_TOKEN) is not configured.")

        if not domain:
            raise CommandError("Domain is required. Pass --domain or set TELEGRAM_WEBHOOK_URL.")

        status = setup_webhook(token, domain)
        if not status:
            raise CommandError("Telegram webhook setup failed.")

        self.stdout.write(self.style.SUCCESS(f"Webhook set successfully for {domain.rstrip('/')}/bot/webhook/"))
