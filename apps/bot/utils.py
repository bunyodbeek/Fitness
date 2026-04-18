from telebot import TeleBot


def setup_webhook(token, domain):
    bot = TeleBot(token)

    bot.remove_webhook()
    url = f"{domain}/bot/webhook/"

    status = bot.set_webhook(url)
    print("Webhook:", "OK" if status else "FAILED", url)

    return status
