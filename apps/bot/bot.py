import telebot
from root.settings import BOT_TOKEN

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
