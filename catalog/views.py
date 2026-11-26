import json
import hashlib
from django.conf import settings
from django.contrib.auth import get_user_model, login, logout
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.utils import timezone
from django.shortcuts import redirect
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Q
from django.middleware.csrf import get_token
from django.http import JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from .models import MagicLink, Opposition, Question, QuestionReport, Topic, UserSettings
from .serializers import serialize_opposition_detail, serialize_opposition_summary


DEFAULT_PAGE_SIZE = 10
MAX_PAGE_SIZE = 100


def _json_payload(request):
    if request.content_type != "application/json":
        return None, JsonResponse(
            {
                "error": {
                    "code": "invalid_content_type",
                    "message": "La solicitud debe enviarse como JSON.",
                }
            },
            status=415,
        )
    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None, JsonResponse(
            {
                "error": {
                    "code": "invalid_json",
                    "message": "El contenido no es JSON válido.",
                }
            },
            status=400,
        )
    if not isinstance(payload, dict):
        return None, JsonResponse(
            {
                "error": {
                    "code": "invalid_request",
                    "message": "La solicitud debe ser un objeto JSON.",
                }
            },
            status=400,
        )
    return payload, None


@require_POST
def request_magic_link(request):
    payload, error_response = _json_payload(request)
    if error_response:
        return error_response

    email = str(payload.get("email", "")).strip().lower()
    purpose = str(payload.get("purpose", "")).strip()
    if purpose not in {"register", "login"}:
        return JsonResponse(
            {
                "error": {
                    "code": "invalid_purpose",
                    "message": "La acción solicitada no es válida.",
                }
            },
            status=400,
        )
    try:
        validate_email(email)
    except ValidationError:
        return JsonResponse(
            {
                "error": {
                    "code": "invalid_email",
                    "message": "Introduce un correo electrónico válido.",
                }
            },
            status=400,
        )

    User = get_user_model()
    user = User.objects.filter(email__iexact=email).first()
    if purpose == "register" and user is None:
        username = email
        if len(username) > 150:
            username = email[:150]
        user = User.objects.create_user(
            username=username,
            email=email,
        )
    elif purpose == "login" and user is None:
        return JsonResponse({
            "message": "Si existe una cuenta con este correo, recibirás un enlace mágico."
        })

    if purpose == "register":
        first_name = str(payload.get("firstName", "")).strip()[:150]
        last_name_parts = [
            str(payload.get("firstSurname", "")).strip(),
            str(payload.get("secondSurname", "")).strip(),
        ]
        user.first_name = first_name
        user.last_name = " ".join(part for part in last_name_parts if part)[:150]
        user.save(update_fields=["first_name", "last_name"])

    token, magic_link = MagicLink.create_for(user, purpose)
    verify_url = request.build_absolute_uri(
        f"/api/auth/magic/verify/{token}"
    )

    text_message = (
        "¡Hola!\n\n"
        "¡Te damos la bienvenida a OposNavarra!\n\n"
        "Hemos creado un enlace mágico seguro, exclusivo para ti. "
        "Haz clic para iniciar sesión sin contraseña:\n"
        f"{verify_url}\n\n"
        "Este enlace caduca en 15 minutos y solo puede utilizarse una vez.\n\n"
        "Saludos cordiales,\nEl equipo de OposNavarra"
    )
    html_message = f"""
<!doctype html>
<html lang="es">
  <body style="margin:0;background:#f3f3f7;font-family:Arial,sans-serif;color:#24243a;">
    <div style="max-width:620px;margin:32px auto;background:#ffffff;border-radius:16px;overflow:hidden;">
      <div style="padding:28px 32px 12px;text-align:center;">
        <div style="font-size:22px;font-weight:800;letter-spacing:1px;">OPOSNAVARRA</div>
      </div>
      <div style="padding:18px 32px 34px;">
        <h1 style="margin:0 0 18px;font-size:28px;text-align:center;">¡Te damos la bienvenida a OposNavarra!</h1>
        <p style="font-size:16px;line-height:1.6;"><strong>¡Hola!</strong></p>
        <p style="font-size:16px;line-height:1.6;">Hemos creado un «enlace mágico» seguro, exclusivo para ti: sin contraseñas que recordar y sin complicaciones.</p>
        <h2 style="font-size:18px;margin-top:24px;">Empieza en segundos</h2>
        <ol style="font-size:15px;line-height:1.65;padding-left:20px;">
          <li>Haz clic en el botón que aparece más abajo.</li>
          <li>Iniciarás sesión automáticamente y podrás empezar a practicar.</li>
        </ol>
        <p style="text-align:center;margin:28px 0;">
          <a href="{verify_url}" style="display:inline-block;padding:15px 26px;border-radius:999px;background:#ff7417;color:#ffffff;text-decoration:none;font-weight:800;">Accede y comienza a practicar</a>
        </p>
        <h2 style="font-size:18px;">¿Qué sigue?</h2>
        <p style="font-size:15px;line-height:1.7;">✓ Realiza tu primer examen de práctica.<br>✓ Prueba nuestro sistema de aprendizaje adaptativo.<br>✓ Consulta tus análisis de progreso personalizados.<br>✓ Explora más de 4000 preguntas de nivel de examen para tu certificación.</p>
        <p style="font-size:13px;color:#77788a;">Este enlace caduca en 15 minutos y solo puede utilizarse una vez.</p>
        <hr style="border:0;border-top:1px solid #ececf2;margin:24px 0;">
        <p style="font-size:14px;line-height:1.6;">¿Tienes alguna pregunta? Estamos aquí para ayudarte: <a href="mailto:support@trustedinstitute.com">support@trustedinstitute.com</a></p>
        <p>Saludos cordiales,<br><strong>El equipo de OposNavarra</strong></p>
      </div>
    </div>
  </body>
</html>
""".strip()
    mail = EmailMultiAlternatives(
        "Tu enlace mágico de OposNavarra",
        text_message,
        settings.DEFAULT_FROM_EMAIL,
        [email],
    )
    mail.attach_alternative(html_message, "text/html")
    mail.send(fail_silently=False)

    return JsonResponse({
        "message": (
            "Revisa tu correo. Hemos enviado un enlace mágico válido durante 15 minutos."
        )
    })


@require_GET
def verify_magic_link(request, token):
    digest = hashlib.sha256(token.encode()).hexdigest()
    now = timezone.now()
    with transaction.atomic():
        magic_link = MagicLink.objects.select_for_update().select_related("user").filter(
            token_digest=digest
        ).first()
        if (
            magic_link is None
            or magic_link.used_at is not None
            or magic_link.expires_at <= now
        ):
            return redirect(f"{settings.FRONTEND_URL}/login?auth=invalid")
        magic_link.used_at = now
        magic_link.save(update_fields=["used_at"])
        login(request, magic_link.user)

    return redirect(f"{settings.FRONTEND_URL}/?auth=magic")


@require_GET
def auth_session(request):
    if not request.user.is_authenticated:
        return JsonResponse({"authenticated": False})
    user_settings, _ = UserSettings.objects.get_or_create(user=request.user)
    return JsonResponse({
        "authenticated": True,
        "user": {
            "email": request.user.email,
            "firstName": request.user.first_name,
            "lastName": request.user.last_name,
            "timezone": user_settings.timezone,
            "nameChanged": user_settings.name_changed,
        },
    })


@require_POST
def update_profile_settings(request):
    if not request.user.is_authenticated:
        return JsonResponse(
            {"error": {"code": "authentication_required", "message": "Inicia sesión para guardar tu perfil."}},
            status=401,
        )
    payload, error_response = _json_payload(request)
    if error_response:
        return error_response

    first_name = payload.get("firstName")
    last_name = payload.get("lastName")
    if not isinstance(first_name, str) or not first_name.strip() or len(first_name.strip()) > 150:
        return JsonResponse(
            {"error": {"code": "invalid_first_name", "message": "Introduce un nombre de hasta 150 caracteres."}},
            status=400,
        )
    if not isinstance(last_name, str) or not last_name.strip() or len(last_name.strip()) > 150:
        return JsonResponse(
            {"error": {"code": "invalid_last_name", "message": "Introduce un apellido de hasta 150 caracteres."}},
            status=400,
        )

    with transaction.atomic():
        user_settings, _ = UserSettings.objects.select_for_update().get_or_create(user=request.user)
        if user_settings.name_changed:
            return JsonResponse(
                {"error": {"code": "name_already_changed", "message": "El nombre del perfil solo se puede cambiar una vez."}},
                status=409,
            )
        request.user.first_name = first_name.strip()
        request.user.last_name = last_name.strip()
        request.user.save(update_fields=["first_name", "last_name"])
        user_settings.name_changed = True
        user_settings.save(update_fields=["name_changed"])

    return JsonResponse({"firstName": request.user.first_name, "lastName": request.user.last_name, "nameChanged": True})


@require_POST
def update_timezone_setting(request):
    if not request.user.is_authenticated:
        return JsonResponse(
            {"error": {"code": "authentication_required", "message": "Inicia sesión para guardar tus preferencias."}},
            status=401,
        )
    payload, error_response = _json_payload(request)
    if error_response:
        return error_response

    timezone_name = payload.get("timezone")
    if not isinstance(timezone_name, str) or len(timezone_name) > 64:
        return JsonResponse(
            {"error": {"code": "invalid_timezone", "message": "Selecciona una zona horaria válida."}},
            status=400,
        )
    try:
        ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, ValueError):
        return JsonResponse(
            {"error": {"code": "invalid_timezone", "message": "Selecciona una zona horaria válida."}},
            status=400,
        )

    UserSettings.objects.update_or_create(
        user=request.user,
        defaults={"timezone": timezone_name},
    )
    return JsonResponse({"timezone": timezone_name})


@require_POST
def auth_logout(request):
    if not request.user.is_authenticated:
        return JsonResponse({"message": "La sesión ya estaba cerrada."})
    logout(request)
    return JsonResponse({"message": "Sesión cerrada correctamente."})


@require_GET
@ensure_csrf_cookie
def csrf_token(request):
    return JsonResponse({"csrfToken": get_token(request)})


@require_GET
def opposition_list(request):
    page_number = request.GET.get("page", "1")
    page_size_value = request.GET.get("pageSize", str(DEFAULT_PAGE_SIZE))
    try:
        page_size = int(page_size_value)
        if page_size < 1 or page_size > MAX_PAGE_SIZE:
            raise ValueError
    except ValueError:
        return JsonResponse(
            {"error": {"code": "invalid_page_size", "message": "pageSize debe estar entre 1 y 100."}},
            status=400,
        )

    oppositions = Opposition.objects.filter(is_active=True).select_related("category")
    search = request.GET.get("search", "").strip()
    category = request.GET.get("category", "").strip()
    if search:
        oppositions = oppositions.filter(
            Q(name__icontains=search) | Q(description__icontains=search)
        )
    if category:
        oppositions = oppositions.filter(
            Q(category__slug__iexact=category) | Q(category__name__iexact=category)
        )

    paginator = Paginator(oppositions, page_size)
    try:
        page = paginator.page(page_number)
    except (EmptyPage, PageNotAnInteger, ValueError):
        return JsonResponse(
            {"error": {"code": "invalid_page", "message": "La página solicitada no existe."}},
            status=400,
        )

    return JsonResponse(
        {
            "items": [serialize_opposition_summary(item) for item in page.object_list],
            "page": page.number,
            "pageSize": page_size,
            "totalItems": paginator.count,
        }
    )


@require_GET
def opposition_detail(request, slug):
    try:
        opposition = Opposition.objects.filter(is_active=True).select_related(
            "category"
        ).prefetch_related("topics", "practice_presets").get(slug=slug)
    except Opposition.DoesNotExist:
        return JsonResponse(
            {
                "error": {
                    "code": "not_found",
                    "message": "La oposición solicitada no existe.",
                }
            },
            status=404,
        )
    return JsonResponse(serialize_opposition_detail(opposition))


@require_GET
def topic_questions(request, opposition_slug, topic_slug):
    try:
        topic = Topic.objects.select_related("opposition").get(
            opposition__slug=opposition_slug,
            opposition__is_active=True,
            slug=topic_slug,
        )
    except Topic.DoesNotExist:
        return JsonResponse(
            {
                "error": {
                    "code": "not_found",
                    "message": "El tema solicitado no existe.",
                }
            },
            status=404,
        )

    questions = list(topic.questions.order_by("?")[:5])
    if len(questions) < 5:
        return JsonResponse(
            {
                "error": {
                    "code": "insufficient_questions",
                    "message": "El tema no tiene cinco preguntas disponibles.",
                    "available": len(questions),
                }
            },
            status=409,
        )

    return JsonResponse(
        {
            "oppositionName": topic.opposition.name,
            "topicName": topic.name,
            "durationMinutes": 5,
            "questionCount": 5,
            "questions": [
                {
                    "id": question.slug,
                    "statement": question.statement,
                    "options": question.options,
                }
                for question in questions
            ],
        }
    )


@require_POST
def report_question(request, opposition_slug, topic_slug, question_slug):
    if request.content_type != "application/json":
        return JsonResponse(
            {
                "error": {
                    "code": "invalid_content_type",
                    "message": "El reporte debe enviarse como JSON.",
                }
            },
            status=415,
        )

    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse(
            {
                "error": {
                    "code": "invalid_json",
                    "message": "El contenido del reporte no es JSON válido.",
                }
            },
            status=400,
        )

    if not isinstance(payload, dict):
        return JsonResponse(
            {
                "error": {
                    "code": "invalid_report",
                    "message": "El reporte debe ser un objeto JSON.",
                }
            },
            status=400,
        )

    reason = payload.get("reason")
    details = payload.get("details", "")
    if reason not in QuestionReport.Reason.values:
        return JsonResponse(
            {
                "error": {
                    "code": "invalid_reason",
                    "message": "Selecciona un motivo válido para el reporte.",
                }
            },
            status=400,
        )
    if not isinstance(details, str) or len(details) > 1000:
        return JsonResponse(
            {
                "error": {
                    "code": "invalid_details",
                    "message": "El comentario debe tener como máximo 1000 caracteres.",
                }
            },
            status=400,
        )

    try:
        question = Question.objects.select_related("topic__opposition").get(
            topic__opposition__slug=opposition_slug,
            topic__opposition__is_active=True,
            topic__slug=topic_slug,
            slug=question_slug,
        )
    except Question.DoesNotExist:
        return JsonResponse(
            {
                "error": {
                    "code": "not_found",
                    "message": "La pregunta solicitada no existe.",
                }
            },
            status=404,
        )

    QuestionReport.objects.create(
        question=question,
        reason=reason,
        details=details.strip(),
    )
    return JsonResponse(
        {"message": "Reporte enviado. Gracias por ayudarnos a mejorar."},
        status=201,
    )
