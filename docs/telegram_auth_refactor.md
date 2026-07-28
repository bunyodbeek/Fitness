# Telegram Mini App auth refactor — "Telegram ID topilmadi" fix

## Root cause
The frontend read the user id from `Telegram.WebApp.initDataUnsafe.user.id`, which is
unreliable (empty on cold start / relaunch / certain launch contexts). When it came
back empty the app showed **"Xato: Telegram ID topilmadi. Botni qayta ishga tushiring."**
The backend also *trusted* a client-supplied `telegram_id` — both unreliable and spoofable.

## New flow (single source of truth)
The frontend now **never reads `initDataUnsafe` for authentication**. It sends the raw,
HMAC-signed `Telegram.WebApp.initData` string to the backend, which validates the
signature, extracts the user, opens a session, and returns a session token.

> Note: this is a **server-rendered Django multi-page app**, so the durable "session
> token" is the Django **session cookie** (auto-attached to every navigation — an
> in-memory JWT would be lost on each full-page load). The backend *also* returns a
> stateless signed token that the frontend keeps in memory and sends as
> `Authorization: Bearer …` on AJAX calls, as a fallback for webviews that drop the
> cross-origin `SameSite=None` cookie.

## Backend changes
- **`apps/utils/telegram_webapp.py`** — added `verify_init_data()` returning
  `(user_dict | None, error_code)` with explicit codes: `missing_init_data`,
  `bad_signature`, `expired`, `no_user`, `server_misconfigured`. HMAC-SHA256 validation
  (secret = `HMAC("WebAppData", bot_token)`) and the 24h `auth_date` check are unchanged.
  `parse_init_data()` is kept as a thin wrapper (still used by gift-claim in `payments.py`).
- **`apps/utils/session_token.py`** (new) — `make_session_token()` / `read_session_token()`
  using Django `signing` (HMAC, no new dependency), 30-day expiry.
- **`apps/utils/drf_auth.py`** (new) — moved `CsrfExemptSessionAuthentication` here and
  added `TelegramTokenAuthentication` (reads `Authorization: Bearer <token>` /
  `X-Session-Token`).
- **`apps/views/users.py`**
  - `TelegramAuthAPIView` (now `/api/auth/telegram`) rewritten: validates `init_data`
    only, logs each failure with its reason code, returns a clear `{success:false, code,
    error}` (HTTP 401) so the frontend can show the "reopen via bot" screen, and returns
    a `token` on success.
  - `QuestionnaireSubmitAPIView` now resolves identity from verified `init_data`
    (falling back to the authenticated session in edit mode), rejects with a code, and
    returns a `token`. User name/photo come from the *verified* init_data, not the client.
- **`apps/urls.py`** — auth endpoint is `path('api/auth/telegram', …, name='auth_telegram')`.
  (The old `api/telegram-auth/` route was removed — nothing referenced it after the migration.)
- **`root/settings.py`** — added a `LOGGING` config wiring the `apps.telegram_auth`
  logger to the console so auth failures are observable.

## Frontend changes
- **`static/js/tg_auth.js`** (new) — shared `window.TgAuth` module: loads after the SDK,
  calls `ready()`/`expand()`, reads raw `initData` **with 3× 300ms retries** for the SDK
  race, POSTs to `/api/auth/telegram`, keeps the token in memory, exposes `authedFetch()`
  (attaches the Bearer token), and renders a friendly Uzbek **"Ilovani bot orqali oching"**
  overlay with a `https://t.me/<bot>?startapp` deep-link button when initData is empty or
  auth is rejected.
- The Telegram SDK is loaded **synchronously in `<head>` before any app code** in
  `base.html`, `animation.html`, and `questionarrie.html`; `tg_auth.js` loads right after.
- **`animation.html`** — entry-point auth now uses `TgAuth.authenticate({silent:true})`
  instead of `initDataUnsafe.user.id`. (`start_param` is still read from `initDataUnsafe`
  — it's a routing param, not authentication data.)
- **`questionarrie.html`** — removed `resolveTelegramId()` / `parseIdFromInitData()` /
  `initDataUnsafe` prefill. Onboarding auto-auths via `TgAuth`; submit sends `init_data`
  (retried) + questionnaire answers via `authedFetch`, stores the returned token, and
  shows the reopen screen on an auth-code failure.
- **`base.html`** — dropped the `initDataUnsafe`/`localStorage` `getTelegramId()` code
  (it was unused elsewhere) and now silently re-establishes the in-memory token on every
  protected page via `TgAuth.authenticate({silent:true})`.

## Bot
Already compliant: the Mini App is opened only via `web_app=` (WebAppInfo) buttons
(persistent keyboard + inline button + gift claim). The only `url=` button is the admin
panel (`/manage/`), a normal web page that needs no initData. Added a comment in
`apps/bot/bot_view.py` to prevent regressions.

## Verification
- HMAC checks: valid→ok, forged→`bad_signature`, empty→`missing_init_data`,
  old→`expired`; token round-trips; bad token→`None`.
- `python manage.py check` clean; existing test suite (4 tests) passes.
