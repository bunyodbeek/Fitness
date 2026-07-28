from django.conf import settings
from django.http import HttpResponse, JsonResponse
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


class PaywallGateMiddleware:
    """7 kunlik bepul muddat tugagach ilovani premium sahifasida qulflaydi.

    Ro'yxatdan o'tgandan 7 kun o'tgan va faol obunasi bo'lmagan foydalanuvchi
    QAYSI sahifani so'rashidan qat'i nazar premium sahifasiga yo'naltiriladi.
    Ochiq qoladigan yagona manzillar — `apps/utils/paywall.py` dagi ro'yxat
    (kirish, onboarding, to'lov zanjiri, Atmos callback, admin panel).

    Nima uchun middleware: qoida BITTA joyda tursin, view va shablonlarga
    tarqalgan `if` lar bo'lmasin. Har bir so'rovda ishlaydi, shuning uchun
    Telegram'da mini app qayta ochilganda ham (sessiya o'rtasida) tekshiruv
    o'tkazib yuborilmaydi.

    Tab router fragmentlari (`?partial=1`) uchun redirect EMAS, ichida
    `location.replace(...)` bo'lgan kichik HTML bo'lagi qaytariladi: `inject()`
    fragmentdagi `<script>` larni qayta ishga tushiradi, shuning uchun brauzer
    to'liq sahifa yuklashiga o'tadi. Oddiy redirect bo'lsa `fetch` unga ergashib,
    butun gate sahifasini tab ichiga joylab qo'yardi. Bu yo'l eskirgan
    `sessionStorage` keshini ham o'zi tuzatadi.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        blocked = self._gate_response(request)
        if blocked is not None:
            return blocked
        return self.get_response(request)

    @staticmethod
    def _is_fragment(request):
        return (
            request.GET.get("partial") == "1"
            or request.headers.get("X-Requested-With") == "XMLHttpRequest"
        )

    def _gate_response(self, request):
        from apps.utils.paywall import (
            gate_url, is_exempt_path, is_exempt_route, user_is_gated,
        )

        path = request.path
        if is_exempt_path(path):
            return None
        if not user_is_gated(getattr(request, "user", None)):
            return None
        if is_exempt_route(path):
            return None

        target = gate_url()

        # Tartib muhim. Fragment tekshiruvi BIRINCHI: tab router'ning `fetch` i
        # `Accept: */*` yuboradi, shuning uchun "HTML so'ramayapti" degan
        # xulosaga kelib uni JSON bilan rad etib bo'lmaydi.
        if self._is_fragment(request):
            return HttpResponse(
                '<script>window.location.replace("%s");</script>' % target,
                content_type="text/html; charset=utf-8",
                headers={"Cache-Control": "no-store"},
            )

        # Yozuv amallari va aniq JSON so'ragan klientlar — redirect emas, 403.
        # Sahifadan sahifaga o'tish (GET) esa DOIM redirect: `Accept` ga qarab
        # qaror qilish mo'rt, chunki uni har bir klient har xil yuboradi.
        accept = request.headers.get("Accept", "")
        wants_json = "application/json" in accept and "text/html" not in accept
        if request.method not in ("GET", "HEAD") or wants_json:
            return JsonResponse(
                {"success": False, "error": "subscription_required", "redirect": target},
                status=403,
            )

        return redirect(target)
