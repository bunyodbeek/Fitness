from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import redirect
from urllib.parse import urlparse


class TelegramFrameMiddleware:
    """
    Telegram mini app sahifalari Telegram klientida (iframe/webview) ochilishi kerak.
    Standart `X-Frame-Options: DENY` esa har qanday frame'ni bloklab, mini app
    "ochilmaydi". Shu sababli mini app sahifalari uchun X-Frame-Options'ni olib
    tashlab, faqat Telegram (va o'zimiz) frame qila olishiga CSP orqali ruxsat beramiz.
    /admin esa himoyalangan (SAMEORIGIN) qoladi.
    """

    FRAME_ANCESTORS = (
        "frame-ancestors 'self' https://web.telegram.org "
        "https://*.telegram.org https://telegram.org tg:;"
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if request.path.startswith("/admin"):
            response["X-Frame-Options"] = "SAMEORIGIN"
        else:
            # X-Frame-Options uchinchi tomon (Telegram) origin'iga ruxsat bera olmaydi,
            # shuning uchun uni olib tashlab, CSP frame-ancestors ishlatamiz.
            try:
                del response["X-Frame-Options"]
            except KeyError:
                pass
            response["Content-Security-Policy"] = self.FRAME_ANCESTORS

        return response


class TelegramLoginRedirectMiddleware:
    """
    If an anonymous browser user hits a LoginRequired view, Django returns a redirect
    to LOGIN_URL. We convert that redirect to Telegram bot URL for HTML browser flows.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if request.user.is_authenticated:
            return response

        if response.status_code not in (301, 302):
            return response

        location = response.get("Location", "")
        if not location:
            return response

        parsed_location_path = urlparse(location).path
        login_url = settings.LOGIN_URL
        login_path = urlparse(login_url).path if login_url.startswith(("http://", "https://")) else login_url
        normalized_login_path = f"/{login_path.strip('/')}"
        is_login_redirect = parsed_location_path.rstrip("/") == normalized_login_path.rstrip("/")

        if not is_login_redirect:
            return response

        if request.path.rstrip("/") in {"/miniapp/questionnaire", "/miniapp/questionnaire/"}:
            return response

        accepts_html = "text/html" in (request.headers.get("Accept", ""))
        if not accepts_html:
            return response

        from apps.utils.telegram_bot_link import get_bot_deeplink

        return redirect(get_bot_deeplink())


class TelegramProfileRedirectMiddleware:
    """
    Foydalanuvchi (masalan, brauzerda shredzville.com orqali) tizimga kirgan, lekin
    unga bog'langan `UserProfile` mavjud bo'lmasligi mumkin. Ko'p view'lar
    `request.user.profile` ga to'g'ridan-to'g'ri murojaat qiladi va bunday holatda
    `UserProfile.DoesNotExist` xatosi yuzaga keladi (DEBUG=True'da xato sahifasi
    ko'rinadi). Bu middleware shu xatoni bitta joyda ushlab, "profil kerak" bo'lgan
    har qanday sahifani Telegram bot'iga (onboarding) yo'naltiradi.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        # Faqat UserProfile.DoesNotExist (request.user.profile murojaatidan) bilan ishlaymiz.
        # Importni shu yerda qilamiz — app'lar yuklanmasdan oldin middleware import bo'lishi mumkin.
        from apps.models import UserProfile

        if not isinstance(exception, UserProfile.DoesNotExist):
            return None

        from apps.utils.telegram_bot_link import get_bot_deeplink

        bot_url = get_bot_deeplink()

        # API / AJAX so'rovlarga JSON qaytaramiz — bu yerda redirect mantiqsiz.
        accepts_html = "text/html" in (request.headers.get("Accept", ""))
        is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"
        if is_ajax or not accepts_html:
            return JsonResponse(
                {
                    "success": False,
                    "error": "profile_required",
                    "redirect": bot_url,
                },
                status=403,
            )

        return redirect(bot_url)
