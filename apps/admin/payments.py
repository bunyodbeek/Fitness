from apps.models import Payment, Subscription
from apps.models.payments import SubscriptionPlan
from django.contrib import admin


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ['user', 'start_date', 'end_date', 'is_active']


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['user', 'status', 'is_auto_payment', 'auto_payment_attempt', 'created_at', 'completed_at']

@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    pass
