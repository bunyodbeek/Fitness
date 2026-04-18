# apps/bot/services.py (yoki tasks.py)
import asyncio
from django.utils import timezone
from apps.models import UserProfile
from .notifications import notify_subscription_expiring, notify_subscription_expired


def process_subscription_alerts():
	now = timezone.now()
	# 3 kun qolganlarni topamiz
	three_days_later = (now + timezone.timedelta(days=3)).date()
	
	profiles = UserProfile.objects.filter(
		subscription__is_active=True,
		subscription__end_date__date=three_days_later
	)
	
	for profile in profiles:
		if profile.telegram_id:
			# Sync contextda async funksiyani chaqirish
			loop = asyncio.new_event_loop()
			asyncio.set_event_loop(loop)
			loop.run_until_complete(
				notify_subscription_expiring(
					telegram_id=profile.telegram_id,
					days_left=3,
					end_date=profile.subscription.end_date.strftime("%d.%m.%Y"),
					auto_renew=profile.payments.filter(is_auto_payment=True).exists()  # Oxirgi to'lovga qarab
				)
			)
			loop.close()