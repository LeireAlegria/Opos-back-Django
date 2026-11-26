from datetime import datetime, timezone as datetime_timezone

import stripe
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction

from .models import Subscription


PLAN_CONFIG = {
    "premium-monthly": "monthly",
}


def configure_stripe():
    stripe.api_key = settings.STRIPE_SECRET_KEY


def get_or_create_subscription_record(user):
    subscription, _ = Subscription.objects.get_or_create(user=user)
    return subscription


def get_or_create_customer(user):
    configure_stripe()
    record = get_or_create_subscription_record(user)
    if record.stripe_customer_id:
        return record.stripe_customer_id

    customer = stripe.Customer.create(
        email=user.email,
        name=f"{user.first_name} {user.last_name}".strip() or None,
        metadata={"django_user_id": str(user.pk)},
    )
    record.stripe_customer_id = customer.id
    record.save(update_fields=["stripe_customer_id", "updated_at"])
    return customer.id


def create_checkout_session(user, plan_id):
    if plan_id not in PLAN_CONFIG:
        return None, "invalid_plan"
    if not settings.STRIPE_SECRET_KEY or not settings.STRIPE_PRICE_ID:
        return None, "stripe_not_configured"

    record = get_or_create_subscription_record(user)
    if record.stripe_subscription_id and record.status in {
        Subscription.Status.ACTIVE,
        Subscription.Status.TRIALING,
        Subscription.Status.PAST_DUE,
    }:
        return None, "subscription_exists"

    customer_id = get_or_create_customer(user)
    configure_stripe()
    session_params = {
        "mode": "subscription",
        "customer": customer_id,
        "client_reference_id": str(user.pk),
        "line_items": [{"price": settings.STRIPE_PRICE_ID, "quantity": 1}],
        "metadata": {
            "django_user_id": str(user.pk),
            "plan": plan_id,
        },
        "subscription_data": {
            "metadata": {
                "django_user_id": str(user.pk),
                "plan": plan_id,
            }
        },
        "success_url": f"{settings.FRONTEND_URL}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
        "cancel_url": f"{settings.FRONTEND_URL}/payment/cancel",
    }
    if settings.STRIPE_FIRST_MONTH_COUPON_ID:
        session_params["discounts"] = [{"coupon": settings.STRIPE_FIRST_MONTH_COUPON_ID}]

    try:
        session = stripe.checkout.Session.create(**session_params)
    except stripe.StripeError:
        return None, "stripe_error"
    return session, None


def create_portal_session(user):
    record = get_or_create_subscription_record(user)
    if not record.stripe_customer_id:
        return None, "no_customer"
    configure_stripe()
    try:
        session = stripe.billing_portal.Session.create(
            customer=record.stripe_customer_id,
            return_url=f"{settings.FRONTEND_URL}/settings",
        )
    except stripe.StripeError:
        return None, "stripe_error"
    return session, None


def _timestamp(value):
    if value is None:
        return None
    return datetime.fromtimestamp(int(value), tz=datetime_timezone.utc)


def find_user_for_subscription(stripe_subscription, fallback_customer_id=None):
    metadata = getattr(stripe_subscription, "metadata", {}) or {}
    user_id = metadata.get("django_user_id")
    if user_id:
        try:
            return get_user_model().objects.filter(pk=int(user_id)).first()
        except (TypeError, ValueError):
            return None

    customer_id = getattr(stripe_subscription, "customer", None) or fallback_customer_id
    if isinstance(customer_id, dict):
        customer_id = customer_id.get("id")
    if customer_id:
        record = Subscription.objects.select_related("user").filter(
            stripe_customer_id=customer_id
        ).first()
        return record.user if record else None
    return None


@transaction.atomic
def upsert_subscription(stripe_subscription, user=None):
    if user is None:
        user = find_user_for_subscription(stripe_subscription)
    if user is None:
        customer_id = getattr(stripe_subscription, "customer", None)
        if isinstance(customer_id, dict):
            customer_id = customer_id.get("id")
        if not customer_id:
            return None
        existing = Subscription.objects.filter(stripe_customer_id=customer_id).select_related("user").first()
        if existing is None:
            return None
        user = existing.user

    record = Subscription.objects.select_for_update().select_related("user").get_or_create(user=user)[0]
    record.stripe_customer_id = getattr(stripe_subscription, "customer", None) or record.stripe_customer_id
    if isinstance(record.stripe_customer_id, dict):
        record.stripe_customer_id = record.stripe_customer_id.get("id")
    record.stripe_subscription_id = getattr(stripe_subscription, "id", None) or record.stripe_subscription_id
    record.status = getattr(stripe_subscription, "status", Subscription.Status.INCOMPLETE)
    record.cancel_at_period_end = bool(getattr(stripe_subscription, "cancel_at_period_end", False))

    period_end = getattr(stripe_subscription, "current_period_end", None)
    if period_end is None:
        items = getattr(stripe_subscription, "items", None)
        data = getattr(items, "data", []) if items else []
        if data:
            period_end = getattr(data[0], "current_period_end", None)
    if period_end is not None:
        record.current_period_end = _timestamp(period_end)

    items = getattr(stripe_subscription, "items", None)
    data = getattr(items, "data", []) if items else []
    if data:
        price = getattr(data[0], "price", None)
        record.stripe_price_id = getattr(price, "id", "") or record.stripe_price_id
    metadata = getattr(stripe_subscription, "metadata", {}) or {}
    record.plan = metadata.get("plan", record.plan or "premium-monthly")
    record.save()
    return record
