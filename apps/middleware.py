from django.conf import settings
from django.shortcuts import redirect
from urllib.parse import urlparse


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

        return redirect(settings.TELEGRAM_BOT_REDIRECT_URL)
