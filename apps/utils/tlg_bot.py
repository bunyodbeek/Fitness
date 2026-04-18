from apps.bot.bot import bot


def bot_send_message(_id: str | int, msg: str) -> bool:
    bot.send_message(_id, msg)
    return True
