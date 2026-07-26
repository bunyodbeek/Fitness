from django.conf import settings
from django.conf.urls.i18n import i18n_patterns
from django.conf.urls.static import static
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.urls import include, path
from django.views.generic.base import RedirectView
from django.views.decorators.csrf import csrf_exempt # Buni qo'shing
from apps.bot.bot_view import TelegramWebhookView# Webhook view funksiyangizni import qiling
from apps.views.miniapp import MiniAppEntryView
from apps.views.payments import AtmosCallbackView

# 1. Tildan mustaqil (prefiksiz) URL'lar
urlpatterns = [
    path('bot/webhook/', csrf_exempt(TelegramWebhookView.as_view()), name='bot_webhook'),
    # Mini App kirish nuqtasi: BotFather'dagi "Main Mini App" (chat ro'yxatidagi OPEN
    # tugmasi) va menu button shu manzilga ishora qiladi — u tilni har safar qayta
    # aniqlaydi, shuning uchun hech qachon eski tilda "qotib" qolmaydi.
    path('app/', MiniAppEntryView.as_view(), name='miniapp_entry'),
    # Atmos to'lov tizimi natija (callback) URL'i — til prefiksisiz
    path('payments/atmos/callback/', AtmosCallbackView.as_view(), name='atmos_callback'),
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
