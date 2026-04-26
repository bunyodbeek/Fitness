from django.conf import settings
from django.conf.urls.i18n import i18n_patterns
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.urls import include, path
from django.views.generic.base import RedirectView
from django.views.decorators.csrf import csrf_exempt # Buni qo'shing
from apps.bot.bot_view import TelegramWebhookView# Webhook view funksiyangizni import qiling

# 1. Tildan mustaqil (prefiksiz) URL'lar
urlpatterns = [
    path('bot/webhook/', csrf_exempt(TelegramWebhookView.as_view()), name='bot_webhook'),
    path('_nested_admin/', include('nested_admin.urls')),
    path('favicon.ico', RedirectView.as_view(url='/static/images/default_exercise.svg', permanent=False)),
]

# 2. Tilda farqlanuvchi URL'lar
urlpatterns += i18n_patterns(
    path('admin/', admin.site.urls),
    path('', include('apps.urls')),
    path('i18n/', include('django.conf.urls.i18n')),
)

# Static & media files
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
urlpatterns += staticfiles_urlpatterns()
