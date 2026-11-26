from django.urls import path

from . import views
from .webhooks import stripe_webhook


urlpatterns = [
    path("checkout/", views.checkout, name="billing-checkout"),
    path("portal/", views.portal, name="billing-portal"),
    path("subscription/", views.subscription_status, name="billing-subscription"),
    path("webhook/", stripe_webhook, name="billing-webhook"),
]
