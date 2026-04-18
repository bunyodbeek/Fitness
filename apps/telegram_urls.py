from django.urls import path
from apps.bot.bot_view import TelegramWebhookView

urlpatterns = [
    path('webhook/', TelegramWebhookView.as_view()),
]