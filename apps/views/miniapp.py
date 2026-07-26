"""Til prefiksisiz Mini App kirish nuqtasi (`/app/`).

Telegram'dagi ikkita kirish nuqtasi — chat ro'yxatidagi **OPEN** tugmasi (BotFather
"Main Mini App") va xabar maydoni yonidagi **menu button** — bitta GLOBAL, o'zgarmas
URL bilan ishlaydi. Agar ularga `/{lang}/miniapp/questionnaire/` kabi til prefiksli
manzil yozilsa, foydalanuvchi ilovada tilni almashtirgandan keyin ham ular doim eski
tilni ochaveradi (aynan shu muammo bor edi). Shuning uchun ular shu manzilga ishora
qiladi, til esa har bir ochilishda shu yerda aniqlanadi:

    1. saqlangan afzallik — `django_language` cookie yoki sessiya (ilovadagi tanlov),
    2. `?lang=` — botda tanlangan til (faqat saqlangan afzallik bo'lmasa),
    3. klient tili (Accept-Language) → `settings.LANGUAGE_CODE`.

Telegram initData'ni URL fragmentida (`#tgWebAppData=...`) uzatadi; brauzerlar
fragmentni redirect manziliga o'zi ko'chiradi (Location'da fragment bo'lmaganda),
shuning uchun bu yerdagi 302 autentifikatsiyani buzmaydi.
"""

from urllib.parse import urlencode

from django.conf import settings
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils import translation
from django.views import View


class MiniAppEntryView(View):
    # `?lang=` — bot tanlagan til; qolgan query paramlar (masalan `edit=1`)
    # o'zgarishsiz uzatiladi.
    LANG_PARAM = "lang"

    def _supported(self, code):
        code = (code or "")[:2].lower()
        valid = {lang[0] for lang in settings.LANGUAGES}
        return code if code in valid else None

    def _stored_language(self, request):
        """Foydalanuvchining o'zi tanlagan til (ilovadagi Settings ekrani)."""
        return self._supported(
            request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME)
            or request.session.get("django_language")
        )

    def get(self, request, *args, **kwargs):
        stored = self._stored_language(request)
        from_bot = self._supported(request.GET.get(self.LANG_PARAM))

        # Saqlangan afzallik ustuvor: bot havolasidagi `?lang=` uni bekor qilmasin,
        # aks holda ilovada til o'zgartirish hech qachon "yopishmaydi".
        lang = stored or from_bot or translation.get_language_from_request(request)
        lang = self._supported(lang) or settings.LANGUAGE_CODE

        params = request.GET.copy()
        params.pop(self.LANG_PARAM, None)

        with translation.override(lang):
            target = reverse("onboarding")
        if params:
            target = f"{target}?{urlencode(params, doseq=True)}"

        response = HttpResponseRedirect(target)
        # Tanlovni yozib qo'yamiz — keyingi ochilishlarda `?lang=` kerak bo'lmaydi
        # va LocaleMiddleware ham shu cookie'ga tayanadi (Django 4+ sessiyani
        # til uchun o'qimaydi).
        if not stored:
            response.set_cookie(
                settings.LANGUAGE_COOKIE_NAME,
                lang,
                max_age=settings.LANGUAGE_COOKIE_AGE,
                path=settings.LANGUAGE_COOKIE_PATH,
                samesite="None",
                secure=True,
            )
        return response
