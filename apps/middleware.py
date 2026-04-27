from django.conf import settings
from django.shortcuts import redirect


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

        login_path = f"/{settings.LOGIN_URL.strip('/')}/"
        if settings.LOGIN_URL.startswith(("http://", "https://")):
            is_login_redirect = settings.LOGIN_URL in location
        else:
            is_login_redirect = login_path in location or f"/{settings.LOGIN_URL.strip('/')}" in location

        if not is_login_redirect:
            return response

        if request.path.rstrip("/") in {"/miniapp/questionnaire", "/miniapp/questionnaire/"}:
            return response

        accepts_html = "text/html" in (request.headers.get("Accept", ""))
        if not accepts_html:
            return response

        return redirect(settings.TELEGRAM_BOT_REDIRECT_URL)
