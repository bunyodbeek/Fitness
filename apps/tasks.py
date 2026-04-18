# import logging
# from datetime import timedelta
#
# from django.utils import timezone
#
# from apps.models import Subscription
#
# logger = logging.getLogger(__name__)
#
#
# @shared_task
# def check_subscriptions_for_renewal():
#     """
#     Har kuni tekshiradi - ertaga tugaydigan obunalarni topadi
#     Cron: Har kuni soat 10:00 da ishga tushadi
#     """
#
#     tomorrow = timezone.now() + timedelta(days=1)
#
#     # Ertaga tugaydigan va auto_renew yoqilgan obunalar
#     subscriptions = Subscription.objects.filter(
#         end_date__date=tomorrow.date(),
#         is_active=True,
#         auto_renew=True,
#         user__payment_method__isnull=False,
#         user__payment_method__is_active=True
#     )
#
#     for subscription in subscriptions:
#         # Birinchi urinish - darhol
#         process_auto_renewal.delay(subscription.id, attempt=1)
#
#     logger.info(f"Found {subscriptions.count()} subscriptions for renewal")
#
#
# @shared_task(bind=True, max_retries=3)
# def process_auto_renewal(self, subscription_id, attempt=1):
#     """
#     Obunani avtomatik yangilash - to'lov yechish
#
#     Args:
#         subscription_id: Subscription ID
#         attempt: Urinish raqami (1, 2, 3)
#     """
#     from bot.notifications import send_notification  # ← Sizning bot kodingiz
#     from payments.click_merchant import ClickAutoPayment
#     from payments.models import Payment, PaymentMethod, Subscription
#
#     try:
#         subscription = Subscription.objects.get(id=subscription_id)
#         user = subscription.user
#         payment_method = user.payment_method
#
#         # Kartaning amal qilish muddatini tekshirish
#         if payment_method.is_expired():
#             logger.warning(f"Card expired for user {user.username}")
#
#             # Telegram xabar
#             if user.telegram_id:
#                 send_notification(
#                     user.telegram_id,
#                     "⚠️ <b>Karta muddati tugagan!</b>\n\n"
#                     f"💳 Karta: ****{payment_method.card_last_four}\n\n"
#                     "Iltimos, yangi karta qo'shing: /start"
#                 )
#
#             subscription.is_active = False
#             subscription.auto_renew = False
#             subscription.save()
#             return
#
#         # Payment yaratish
#         payment = Payment.objects.create(
#             user=user,
#             subscription=subscription,
#             payment_type='subscription_auto',
#             amount=subscription.price,
#             status='pending',
#             is_auto_payment=True,
#             auto_payment_attempt=attempt
#         )
#
#         # Click orqali to'lov
#         click = ClickAutoPayment()
#         response = click.charge_card(
#             payment_method=payment_method,
#             amount=subscription.price,
#             payment_id=payment.id
#         )
#
#         # Javobni tekshirish
#         if response.get('error') == 0:
#             # ✅ MUVAFFAQIYATLI
#             payment.mark_as_completed()
#             payment.click_trans_id = response.get('click_trans_id')
#             payment.metadata = response
#             payment.save()
#
#             # Obunani uzaytirish
#             subscription.end_date = subscription.end_date + timedelta(days=30)
#             subscription.reset_failed_attempts()
#             subscription.save()
#
#             logger.info(f"Auto-renewal successful for {user.username}")
#
#             # Telegram xabar
#             if user.telegram_id:
#                 send_notification(
#                     user.telegram_id,
#                     f"✅ <b>To'lov muvaffaqiyatli!</b>\n\n"
#                     f"💰 Summa: <b>{payment.amount:,.0f} UZS</b>\n"
#                     f"📅 Obuna tugash sanasi: <b>{subscription.end_date.strftime('%d.%m.%Y')}</b>\n\n"
#                     "Rahmat! 🎉"
#                 )
#
#         else:
#             # ❌ MUVAFFAQIYATSIZ
#             payment.mark_as_failed()
#             payment.metadata = response
#             payment.save()
#
#             logger.error(f"Payment failed for {user.username}, attempt {attempt}")
#
#             # Qayta urinish
#             if attempt < 3:
#                 # 24 soatdan keyin qayta urining
#                 process_auto_renewal.apply_async(
#                     args=[subscription_id, attempt + 1],
#                     countdown=86400  # 24 soat
#                 )
#
#                 # Telegram xabar
#                 if user.telegram_id:
#                     send_notification(
#                         user.telegram_id,
#                         f"⚠️ <b>To'lov amalga oshmadi!</b>\n\n"
#                         f"🔄 Urinish: {attempt}/3\n"
#                         f"⏰ Keyingi urinish: 24 soatdan keyin\n\n"
#                         "Kartangizda yetarli mablag' borligini tekshiring."
#                     )
#             else:
#                 # 3 marta muvaffaqiyatsiz - obunani bekor qilish
#                 subscription.is_active = False
#                 subscription.auto_renew = False
#                 subscription.save()
#
#                 logger.error(f"Subscription cancelled for {user.username}")
#
#                 # Telegram xabar
#                 if user.telegram_id:
#                     send_notification(
#                         user.telegram_id,
#                         "❌ <b>Obuna bekor qilindi!</b>\n\n"
#                         "3 marta to'lov amalga oshmadi.\n"
#                         "Premium funksiyalar yopildi.\n\n"
#                         "Qayta obuna bo'lish: /start"
#                     )
#
#     except Subscription.DoesNotExist:
#         logger.error(f"Subscription {subscription_id} not found")
#     except Exception as e:
#         logger.error(f"Error in auto-renewal: {str(e)}")
#         raise self.retry(exc=e, countdown=3600)
#
#
# @shared_task
# def send_expiry_reminders():
#     """
#     Obuna tugashidan 3 kun oldin eslatma
#     Cron: Har kuni soat 9:00 da
#     """
#     from bot.notifications import send_notification
#     from payments.models import Subscription
#
#     three_days_later = timezone.now() + timedelta(days=3)
#
#     subscriptions = Subscription.objects.filter(
#         end_date__date=three_days_later.date(),
#         is_active=True
#     )
#
#     for subscription in subscriptions:
#         user = subscription.user
#
#         if not user.telegram_id:
#             continue
#
#         if subscription.auto_renew:
#             message = (
#                 "🔔 <b>Eslatma</b>\n\n"
#                 f"Obuna tugashiga <b>3 kun</b> qoldi.\n"
#                 f"📅 Tugash sanasi: {subscription.end_date.strftime('%d.%m.%Y')}\n\n"
#                 "Avtomatik yangilanish yoqilgan ✅"
#             )
#         else:
#             message = (
#                 "🔔 <b>Eslatma</b>\n\n"
#                 f"Obuna tugashiga <b>3 kun</b> qoldi.\n"
#                 f"📅 Tugash sanasi: {subscription.end_date.strftime('%d.%m.%Y')}\n\n"
#                 "Obunani uzaytirish: /start"
#             )
#
#         send_notification(user.telegram_id, message)
#         logger.info(f"Reminder sent to {user.username}")
#
#
# @shared_task
# def deactivate_expired_subscriptions():
#     """
#     Muddati o'tgan obunalarni deaktiv qilish
#     Cron: Har soat
#     """
#     from bot.notifications import send_notification
#     from payments.models import Subscription
#
#     expired_subscriptions = Subscription.objects.filter(
#         end_date__lt=timezone.now(),
#         is_active=True
#     )
#
#     for subscription in expired_subscriptions:
#         subscription.is_active = False
#         subscription.save()
#
#         user = subscription.user
#
#         # Telegram xabar
#         if user.telegram_id:
#             send_notification(
#                 user.telegram_id,
#                 "⏰ <b>Obuna muddati tugadi</b>\n\n"
#                 "Premium funksiyalar yopildi.\n\n"
#                 "Qayta obuna bo'lish: /start"
#             )
#
#         logger.info(f"Deactivated subscription for {user.username}")
#
#     logger.info(f"Deactivated {expired_subscriptions.count()} expired subscriptions")
