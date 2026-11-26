from django.conf import settings
from django.db import models
from django.utils import timezone


class Subscription(models.Model):
    class Status(models.TextChoices):
        INCOMPLETE = "incomplete", "Incompleta"
        INCOMPLETE_EXPIRED = "incomplete_expired", "Incompleta caducada"
        TRIALING = "trialing", "Periodo de prueba"
        ACTIVE = "active", "Activa"
        PAST_DUE = "past_due", "Pago pendiente"
        CANCELED = "canceled", "Cancelada"
        UNPAID = "unpaid", "Impagada"
        PAUSED = "paused", "Pausada"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="billing_subscription",
    )
    stripe_customer_id = models.CharField(max_length=255, unique=True, null=True, blank=True)
    stripe_subscription_id = models.CharField(max_length=255, unique=True, null=True, blank=True)
    stripe_price_id = models.CharField(max_length=255, blank=True)
    plan = models.CharField(max_length=64, default="premium-monthly")
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.INCOMPLETE)
    current_period_end = models.DateTimeField(null=True, blank=True)
    cancel_at_period_end = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def has_premium_access(self):
        return self.status in {
            self.Status.ACTIVE,
            self.Status.TRIALING,
            self.Status.PAST_DUE,
        }

    def __str__(self):
        return f"{self.user} - {self.plan} - {self.status}"


class StripeEvent(models.Model):
    event_id = models.CharField(max_length=255, unique=True)
    event_type = models.CharField(max_length=255)
    processed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-processed_at"]
