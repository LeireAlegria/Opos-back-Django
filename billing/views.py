import json

from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from .models import Subscription
from .services import create_checkout_session, create_portal_session


def _json_payload(request):
    if request.content_type != "application/json":
        return None, JsonResponse(
            {"error": {"code": "invalid_content_type", "message": "La solicitud debe enviarse como JSON."}},
            status=415,
        )
    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None, JsonResponse(
            {"error": {"code": "invalid_json", "message": "El contenido no es JSON válido."}},
            status=400,
        )
    if not isinstance(payload, dict):
        return None, JsonResponse(
            {"error": {"code": "invalid_request", "message": "La solicitud debe ser un objeto JSON."}},
            status=400,
        )
    return payload, None


def _subscription_payload(record):
    if record is None:
        return {
            "plan": None,
            "status": None,
            "currentPeriodEnd": None,
            "cancelAtPeriodEnd": False,
            "premiumAvailable": False,
        }
    return {
        "plan": record.plan,
        "status": record.status,
        "currentPeriodEnd": record.current_period_end.isoformat() if record.current_period_end else None,
        "cancelAtPeriodEnd": record.cancel_at_period_end,
        "premiumAvailable": record.has_premium_access(),
    }


@require_POST
def checkout(request):
    if not request.user.is_authenticated:
        return JsonResponse(
            {"error": {"code": "authentication_required", "message": "Inicia sesión para contratar el plan."}},
            status=401,
        )
    payload, error_response = _json_payload(request)
    if error_response:
        return error_response

    plan_id = payload.get("planId") or payload.get("plan")
    session, error = create_checkout_session(request.user, plan_id)
    if error == "invalid_plan":
        return JsonResponse(
            {"error": {"code": "invalid_plan", "message": "El plan seleccionado no está disponible."}},
            status=400,
        )
    if error == "subscription_exists":
        return JsonResponse(
            {"error": {"code": "subscription_exists", "message": "Ya tienes una suscripción activa."}},
            status=409,
        )
    if error == "stripe_not_configured":
        return JsonResponse(
            {"error": {"code": "stripe_not_configured", "message": "El servicio de pago no está configurado."}},
            status=503,
        )
    if error:
        return JsonResponse(
            {"error": {"code": "stripe_error", "message": "No se pudo iniciar el pago."}},
            status=502,
        )
    return JsonResponse({"url": session.url})


@require_POST
def portal(request):
    if not request.user.is_authenticated:
        return JsonResponse(
            {"error": {"code": "authentication_required", "message": "Inicia sesión para gestionar tu suscripción."}},
            status=401,
        )
    session, error = create_portal_session(request.user)
    if error == "no_customer":
        return JsonResponse(
            {"error": {"code": "no_customer", "message": "Todavía no existe un cliente de facturación."}},
            status=404,
        )
    if error:
        return JsonResponse(
            {"error": {"code": "stripe_error", "message": "No se pudo abrir el portal de facturación."}},
            status=502,
        )
    return JsonResponse({"url": session.url})


@require_GET
def subscription_status(request):
    if not request.user.is_authenticated:
        return JsonResponse(
            {"error": {"code": "authentication_required", "message": "Inicia sesión para consultar tu suscripción."}},
            status=401,
        )
    record = Subscription.objects.filter(user=request.user).first()
    return JsonResponse(_subscription_payload(record))
