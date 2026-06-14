from django.conf import settings
from django.conf.urls.i18n import i18n_patterns
from django.conf.urls.static import static
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.urls import include, path
from django.views.generic.base import RedirectView
from django.views.decorators.csrf import csrf_exempt # Buni qo'shing
from apps.bot.bot_view import TelegramWebhookView# Webhook view funksiyangizni import qiling

# 1. Tildan mustaqil (prefiksiz) URL'lar
urlpatterns = [
    path('bot/webhook/', csrf_exempt(TelegramWebhookView.as_view()), name='bot_webhook'),
    path('favicon.ico', RedirectView.as_view(url='/static/images/default_exercise.svg', permanent=False)),
]

# 2. Tilda farqlanuvchi URL'lar
urlpatterns += i18n_patterns(
    # Custom admin panel (Django's default /admin/ is removed)
    path('manage/', include('apps.panel.urls')),
    path('', include('apps.urls')),
    path('i18n/', include('django.conf.urls.i18n')),
)

# Static & media files
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
urlpatterns += staticfiles_urlpatterns()
