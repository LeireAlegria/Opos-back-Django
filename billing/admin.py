from django.contrib import admin

from .models import StripeEvent, Subscription


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ("user", "plan", "status", "stripe_customer_id", "stripe_subscription_id", "current_period_end")
    list_filter = ("status", "plan", "cancel_at_period_end")
    search_fields = ("user__email", "stripe_customer_id", "stripe_subscription_id")


@admin.register(StripeEvent)
class StripeEventAdmin(admin.ModelAdmin):
    list_display = ("event_id", "event_type", "processed_at")
    search_fields = ("event_id", "event_type")
