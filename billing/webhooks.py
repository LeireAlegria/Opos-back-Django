import logging

import stripe
from django.conf import settings
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import StripeEvent, Subscription
from .services import configure_stripe, upsert_subscription

logger = logging.getLogger(__name__)


def _subscription_from_invoice(invoice):
    subscription_id = getattr(invoice, "subscription", None)
    if isinstance(subscription_id, dict):
        subscription_id = subscription_id.get("id")
    if not subscription_id:
        customer_id = getattr(invoice, "customer", None)
        if isinstance(customer_id, dict):
            customer_id = customer_id.get("id")
        record = Subscription.objects.filter(stripe_customer_id=customer_id).first()
        return record
    configure_stripe()
    try:
        return stripe.Subscription.retrieve(subscription_id)
    except stripe.StripeError:
        return None


@csrf_exempt
@require_POST
def stripe_webhook(request):
    payload = request.body
    signature = request.META.get("HTTP_STRIPE_SIGNATURE")
    if not signature or not settings.STRIPE_WEBHOOK_SECRET:
        return HttpResponse(status=400)

    configure_stripe()
    try:
        event = stripe.Webhook.construct_event(
            payload,
            signature,
            settings.STRIPE_WEBHOOK_SECRET,
        )
    except (stripe.SignatureVerificationError, ValueError):
        return HttpResponse(status=400)

    try:
        with transaction.atomic():
            _, created = StripeEvent.objects.get_or_create(
                event_id=event["id"],
                defaults={"event_type": event["type"]},
            )
            if not created:
                return JsonResponse({"received": True, "duplicate": True})

            event_type = event["type"]
            data_object = event["data"]["object"]

            if event_type == "checkout.session.completed":
                subscription_id = data_object.get("subscription")
                if subscription_id:
                    configure_stripe()
                    subscription = stripe.Subscription.retrieve(subscription_id)
                    metadata = subscription.metadata or {}
                    user_id = metadata.get("django_user_id")
                    if not user_id:
                        user_id = data_object.get("client_reference_id")
                    if user_id:
                        from django.contrib.auth import get_user_model
                        user = get_user_model().objects.filter(pk=int(user_id)).first()
                        upsert_subscription(subscription, user)

            elif event_type in {
                "customer.subscription.created",
                "customer.subscription.updated",
                "customer.subscription.deleted",
            }:
                upsert_subscription(data_object)

            elif event_type == "invoice.paid":
                subscription = _subscription_from_invoice(data_object)
                if hasattr(subscription, "id") and hasattr(subscription, "status"):
                    upsert_subscription(subscription)

            elif event_type == "invoice.payment_failed":
                subscription = _subscription_from_invoice(data_object)
                if hasattr(subscription, "id"):
                    record = upsert_subscription(subscription)
                    if record is not None:
                        record.status = Subscription.Status.PAST_DUE
                        record.save(update_fields=["status", "updated_at"])
    except Exception:
        logger.exception("Stripe webhook processing failed", extra={"event_id": event["id"]})
        raise

    return JsonResponse({"received": True})
