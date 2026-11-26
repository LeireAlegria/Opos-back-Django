import json
from types import SimpleNamespace
from unittest.mock import patch

import stripe
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import StripeEvent, Subscription


@override_settings(
    STRIPE_SECRET_KEY="sk_test_example",
    STRIPE_PRICE_ID="price_test",
    STRIPE_FIRST_MONTH_COUPON_ID="coupon_test",
    STRIPE_WEBHOOK_SECRET="whsec_test",
    FRONTEND_URL="http://localhost:5173",
)
class CheckoutTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="billing@example.com",
            email="billing@example.com",
        )
        self.client.force_login(self.user)

    def test_requires_authentication(self):
        client = self.client_class()
        response = client.post(
            reverse("billing-checkout"),
            data=json.dumps({"planId": "premium-monthly"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)

    def test_rejects_unknown_plan(self):
        response = self.client.post(
            reverse("billing-checkout"),
            data=json.dumps({"planId": "free"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "invalid_plan")

    @patch("billing.services.stripe.checkout.Session.create")
    @patch("billing.services.stripe.Customer.create")
    def test_creates_checkout_session(self, customer_create, session_create):
        customer_create.return_value = SimpleNamespace(id="cus_test")
        session_create.return_value = SimpleNamespace(
            id="cs_test",
            url="https://checkout.stripe.com/c/pay/cs_test",
        )

        response = self.client.post(
            reverse("billing-checkout"),
            data=json.dumps({"planId": "premium-monthly"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["url"], "https://checkout.stripe.com/c/pay/cs_test")
        params = session_create.call_args.kwargs
        self.assertEqual(params["mode"], "subscription")
        self.assertEqual(params["discounts"], [{"coupon": "coupon_test"}])
        self.assertEqual(params["client_reference_id"], str(self.user.pk))

    def test_prevents_duplicate_active_subscription(self):
        record = Subscription.objects.create(
            user=self.user,
            stripe_subscription_id="sub_test",
            status=Subscription.Status.ACTIVE,
        )
        response = self.client.post(
            reverse("billing-checkout"),
            data=json.dumps({"planId": "premium-monthly"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"]["code"], "subscription_exists")
        record.refresh_from_db()

    @patch("billing.services.stripe.billing_portal.Session.create")
    def test_creates_portal_session(self, portal_create):
        Subscription.objects.create(
            user=self.user,
            stripe_customer_id="cus_test",
        )
        portal_create.return_value = SimpleNamespace(
            url="https://billing.stripe.com/session/test",
        )
        response = self.client.post(reverse("billing-portal"), data="{}", content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["url"], "https://billing.stripe.com/session/test")


@override_settings(STRIPE_SECRET_KEY="sk_test_example", STRIPE_WEBHOOK_SECRET="whsec_test")
class WebhookTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="webhook@example.com",
            email="webhook@example.com",
        )

    @patch("billing.webhooks.stripe.Webhook.construct_event")
    def test_subscription_updated_updates_access(self, construct_event):
        construct_event.return_value = {
            "id": "evt_test_1",
            "type": "customer.subscription.updated",
            "data": {
                "object": SimpleNamespace(
                    id="sub_test",
                    customer="cus_test",
                    status="active",
                    cancel_at_period_end=True,
                    current_period_end=2000000000,
                    metadata={"django_user_id": str(self.user.pk), "plan": "premium-monthly"},
                    items=SimpleNamespace(data=[SimpleNamespace(price=SimpleNamespace(id="price_test"))]),
                )
            },
        }
        response = self.client.post(
            reverse("billing-webhook"),
            data="{}",
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="sig_test",
        )
        self.assertEqual(response.status_code, 200)
        record = Subscription.objects.get(user=self.user)
        self.assertTrue(record.has_premium_access())
        self.assertTrue(record.cancel_at_period_end)
        self.assertEqual(record.status, Subscription.Status.ACTIVE)

    @patch("billing.webhooks.stripe.Webhook.construct_event")
    def test_duplicate_event_is_processed_once(self, construct_event):
        construct_event.return_value = {
            "id": "evt_duplicate",
            "type": "customer.subscription.deleted",
            "data": {
                "object": SimpleNamespace(
                    id="sub_deleted",
                    customer="cus_deleted",
                    status="canceled",
                    cancel_at_period_end=False,
                    metadata={"django_user_id": str(self.user.pk), "plan": "premium-monthly"},
                )
            },
        }
        first = self.client.post(
            reverse("billing-webhook"), data="{}", content_type="application/json",
            HTTP_STRIPE_SIGNATURE="sig_test",
        )
        second = self.client.post(
            reverse("billing-webhook"), data="{}", content_type="application/json",
            HTTP_STRIPE_SIGNATURE="sig_test",
        )
        self.assertEqual(first.status_code, 200)
        self.assertTrue(second.json()["duplicate"])
        self.assertEqual(StripeEvent.objects.filter(event_id="evt_duplicate").count(), 1)
        record = Subscription.objects.get(user=self.user)
        self.assertFalse(record.has_premium_access())

    @patch("billing.webhooks.stripe.Webhook.construct_event")
    def test_invalid_signature_is_rejected(self, construct_event):
        construct_event.side_effect = stripe.SignatureVerificationError("invalid", "header")
        response = self.client.post(
            reverse("billing-webhook"),
            data="{}",
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="bad",
        )
        self.assertEqual(response.status_code, 400)
