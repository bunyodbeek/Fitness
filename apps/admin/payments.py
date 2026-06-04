from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from apps.models.payments import SubscriptionPlan, Subscription, Payment


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
	list_display = ('get_period_display', 'price_uzs', 'price_usd', 'is_popular', 'is_active', 'order')
	list_editable = ('price_uzs', 'price_usd', 'is_popular', 'is_active', 'order')
	list_filter = ('is_active', 'is_popular')
	search_fields = ('period',)        # <-- add this line

	ordering = ('order',)

	fieldsets = (
		(_("Tarif"), {'fields': ('period', 'order')}),
		(_("Narxlar (mustaqil)"), {
			'fields': ('price_uzs', 'price_usd'),
			'description': _("UZS va USD narxlari bir-biriga bog‘liq emas — har birini alohida belgilang."),
		}),
		(_("Holat"), {'fields': ('is_popular', 'is_active')}),
	)


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
	list_display = ('user', 'plan', 'start_date', 'end_date', 'is_active', 'days_remaining')
	list_filter = ('is_active', 'plan')
	search_fields = ('user__name', 'user__telegram_id')
	readonly_fields = ('start_date', 'end_date')
	autocomplete_fields = ('user',)


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
	list_display = ('user', 'plan', 'amount', 'currency', 'method', 'status', 'created_at')
	list_filter = ('status', 'currency', 'method')
	search_fields = ('user__name', 'user__telegram_id', 'payme_id')
	readonly_fields = ('created_at', 'completed_at', 'created_at_ms', 'perform_time', 'cancel_time')
	autocomplete_fields = ('user', 'plan', 'subscription')
	actions = ('mark_completed', 'mark_failed')

	@admin.action(description=_("Tanlanganlarni bajarildi deb belgilash"))
	def mark_completed(self, request, queryset):
		for p in queryset:
			p.mark_as_completed()

	@admin.action(description=_("Tanlanganlarni bekor qilish"))
	def mark_failed(self, request, queryset):
		for p in queryset:
			p.mark_as_failed()