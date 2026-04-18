# Telegram bot troubleshooting

If your bot does not respond, check these items in order:

1. **Token configured**
   - Add `TELEGRAM_BOT_TOKEN` to `.env`.
   - Do not hardcode token in source code.

2. **Public HTTPS domain**
   - Telegram webhook only works with a public HTTPS URL.
   - Set `TELEGRAM_WEBHOOK_URL=https://your-domain.com`.

3. **Webhook setup**
   - Run:
     ```bash
     python manage.py set_telegram_webhook --domain https://your-domain.com
     ```
   - Expected webhook endpoint: `https://your-domain.com/bot/webhook/`

4. **URL must exist in Django**
   - Endpoint should be routed in `root/urls.py`.

5. **Test from Telegram API**
   - `getWebhookInfo` should show your current webhook and no errors.

6. **Process and logs**
   - Ensure Django app is running and reachable from internet.
   - Check server logs when sending `/start`.
