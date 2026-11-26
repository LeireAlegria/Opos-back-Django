from django.db import models
from django.conf import settings
import hashlib
import secrets
from django.utils import timezone
from datetime import timedelta


class MagicLink(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="magic_links",
    )
    email = models.EmailField()
    token_digest = models.CharField(max_length=64, unique=True, editable=False)
    purpose = models.CharField(max_length=16)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    @classmethod
    def create_for(cls, user, purpose, lifetime_minutes=15):
        token = secrets.token_urlsafe(32)
        digest = hashlib.sha256(token.encode()).hexdigest()
        record = cls.objects.create(
            user=user,
            email=user.email,
            purpose=purpose,
            token_digest=digest,
            expires_at=timezone.now() + timedelta(minutes=lifetime_minutes),
        )
        return token, record


class UserSettings(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="catalog_settings",
    )
    timezone = models.CharField(max_length=64, default="Europe/Madrid")
    name_changed = models.BooleanField(default=False)

    def __str__(self):
        return f"Preferencias de {self.user}"


class Category(models.Model):
    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Nombre de la categoría que se mostrará en el catálogo.",
    )
    slug = models.SlugField(
        max_length=100,
        unique=True,
        help_text="Identificador único para usar la categoría en las direcciones web.",
    )

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name


class Opposition(models.Model):
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="oppositions",
        help_text="Categoría a la que pertenece esta oposición.",
    )
    slug = models.SlugField(
        max_length=120,
        unique=True,
        help_text="Identificador único de la oposición usado en su URL.",
    )
    name = models.CharField(
        max_length=160,
        help_text="Nombre de la oposición que se mostrará al alumnado.",
    )
    icon = models.CharField(
        max_length=20,
        blank=True,
        help_text="Emoji o icono breve para identificar la oposición; es opcional.",
    )
    color = models.CharField(
        max_length=7,
        blank=True,
        help_text="Color opcional en formato hexadecimal, por ejemplo #397FA5.",
    )
    description = models.TextField(
        blank=True,
        help_text="Descripción breve que aparecerá en la ficha de la oposición.",
    )
    question_count = models.PositiveIntegerField(
        default=0,
        help_text="Número total de preguntas disponibles para esta oposición.",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Indica si la oposición se publica y aparece en la API.",
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Topic(models.Model):
    opposition = models.ForeignKey(
        Opposition,
        on_delete=models.CASCADE,
        related_name="topics",
        help_text="Oposición a la que pertenece este tema.",
    )
    slug = models.SlugField(
        max_length=120,
        help_text="Identificador del tema dentro de la oposición; se usa en su URL.",
    )
    name = models.CharField(
        max_length=160,
        help_text="Nombre del tema que se mostrará en el catálogo.",
    )
    question_count = models.PositiveIntegerField(
        default=0,
        help_text="Número de preguntas disponibles para este tema.",
    )
    concepts = models.JSONField(
        default=list,
        blank=True,
        help_text="Lista de conceptos clave del tema, por ejemplo [\"traslado\", \"movilización\"].",
    )

    class Meta:
        ordering = ["name"]
        verbose_name = "tema"
        verbose_name_plural = "Temas"
        constraints = [
            models.UniqueConstraint(
                fields=["opposition", "slug"], name="unique_topic_per_opposition"
            )
        ]

    def __str__(self):
        return self.name


class Question(models.Model):
    topic = models.ForeignKey(
        Topic,
        on_delete=models.CASCADE,
        related_name="questions",
        help_text="Tema al que pertenece esta pregunta.",
    )
    slug = models.SlugField(
        max_length=120,
        help_text="Identificador de la pregunta dentro del tema.",
    )
    statement = models.TextField(help_text="Enunciado de la pregunta.")
    options = models.JSONField(
        help_text="Opciones de respuesta como una lista de objetos con id y texto."
    )
    correct_option = models.CharField(
        max_length=1,
        help_text="Identificador de la opción correcta.",
    )

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(
                fields=["topic", "slug"], name="unique_question_per_topic"
            )
        ]

    def __str__(self):
        return self.statement


class QuestionReport(models.Model):
    class Reason(models.TextChoices):
        INCORRECT = "incorrect", "Respuesta incorrecta"
        UNCLEAR = "unclear", "Enunciado confuso"
        TYPO = "typo", "Error de redacción"
        OTHER = "other", "Otro problema"

    class Status(models.TextChoices):
        PENDING = "pending", "Pendiente"
        REVIEWED = "reviewed", "Revisado"

    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name="reports",
        help_text="Pregunta reportada.",
    )
    reason = models.CharField(
        max_length=12,
        choices=Reason.choices,
        help_text="Motivo del reporte.",
    )
    details = models.CharField(
        max_length=1000,
        blank=True,
        help_text="Comentario opcional de quien reporta.",
    )
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.PENDING,
        help_text="Estado de revisión del reporte.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Reporte de {self.question} ({self.get_reason_display()})"


class PracticePreset(models.Model):
    class Mode(models.TextChoices):
        EASY = "easy", "Fácil"
        DIFFICULT = "difficult", "Difícil"
        FULL = "full", "Examen completo"

    opposition = models.ForeignKey(
        Opposition,
        on_delete=models.CASCADE,
        related_name="practice_presets",
        help_text="Oposición a la que pertenece esta modalidad de práctica.",
    )
    mode = models.CharField(
        max_length=12,
        choices=Mode.choices,
        help_text="Tipo de práctica: fácil, difícil o examen completo.",
    )
    question_count = models.PositiveIntegerField(
        help_text="Número de preguntas incluidas en esta práctica.",
    )
    duration_minutes = models.PositiveIntegerField(
        help_text="Duración de la práctica en minutos.",
    )
    mock_number = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Número del examen completo; solo se utiliza en ese modo.",
    )
    mock_id = models.SlugField(
        max_length=80,
        blank=True,
        help_text="Identificador del examen completo para la URL; es opcional.",
    )

    class Meta:
        ordering = ["mode", "mock_number"]
        verbose_name = "modalidad de práctica"
        verbose_name_plural = "Modalidades de práctica"
        constraints = [
            models.UniqueConstraint(
                fields=["opposition", "mode", "mock_number"],
                name="unique_practice_preset",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(mode="full", mock_number__isnull=False)
                    | (
                        ~models.Q(mode="full")
                        & models.Q(mock_number__isnull=True)
                    )
                ),
                name="full_practice_requires_mock_number",
            ),
        ]

    def __str__(self):
        return f"{self.opposition} - {self.get_mode_display()}"
