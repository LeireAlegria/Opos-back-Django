from django.contrib import admin, messages
from django.db.models import Count

from .models import (
    Category,
    Opposition,
    PracticePreset,
    Question,
    QuestionReport,
    Topic,
)


class TopicInline(admin.TabularInline):
    model = Topic
    fields = ("name", "slug", "question_count", "concepts")
    prepopulated_fields = {"slug": ("name",)}
    extra = 0
    show_change_link = True
    verbose_name = "tema"
    verbose_name_plural = "Temas"


class PracticePresetInline(admin.TabularInline):
    model = PracticePreset
    fields = (
        "mode",
        "question_count",
        "duration_minutes",
        "mock_number",
        "mock_id",
    )
    extra = 0
    show_change_link = True
    verbose_name = "modalidad de práctica"
    verbose_name_plural = "Modalidades de práctica"


@admin.register(Opposition)
class OppositionAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "category",
        "question_count",
        "topic_count",
        "practice_count",
        "is_active",
    )
    list_display_links = ("name",)
    list_editable = ("question_count", "is_active")
    list_filter = ("category", "is_active")
    list_select_related = ("category",)
    list_per_page = 25
    search_fields = ("name", "slug", "description", "category__name")
    ordering = ("name",)
    prepopulated_fields = {"slug": ("name",)}
    save_on_top = True
    fieldsets = (
        (
            "Datos de la oposición",
            {
                "fields": ("name", "slug", "category", "is_active"),
                "description": "Nombre, dirección web y categoría que verá el alumnado.",
            },
        ),
        (
            "Presentación",
            {
                "fields": ("icon", "color", "description"),
                "description": "Personaliza el icono, el color y el texto de la ficha.",
            },
        ),
        (
            "Contenido",
            {
                "fields": ("question_count",),
                "description": "Total de preguntas disponibles para esta oposición.",
            },
        ),
    )
    inlines = [TopicInline, PracticePresetInline]
    actions = ("activate_oppositions", "deactivate_oppositions")
    verbose_name = "oposición"
    verbose_name_plural = "Oposiciones"

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            _topic_count=Count("topics", distinct=True),
            _practice_count=Count("practice_presets", distinct=True),
        )

    @admin.display(description="Temas", ordering="_topic_count")
    def topic_count(self, opposition):
        return opposition._topic_count

    @admin.display(description="Prácticas", ordering="_practice_count")
    def practice_count(self, opposition):
        return opposition._practice_count

    @admin.action(description="Activar oposiciones seleccionadas")
    def activate_oppositions(self, request, queryset):
        updated_count = queryset.update(is_active=True)
        self.message_user(
            request,
            f"Se activaron {updated_count} oposiciones.",
            messages.SUCCESS,
        )

    @admin.action(description="Desactivar oposiciones seleccionadas")
    def deactivate_oppositions(self, request, queryset):
        updated_count = queryset.update(is_active=False)
        self.message_user(
            request,
            f"Se desactivaron {updated_count} oposiciones.",
            messages.SUCCESS,
        )


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "opposition_count")
    list_display_links = ("name",)
    list_per_page = 25
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("name",)
    verbose_name = "categoría"
    verbose_name_plural = "Categorías"

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            _opposition_count=Count("oppositions", distinct=True)
        )

    @admin.display(description="Oposiciones", ordering="_opposition_count")
    def opposition_count(self, category):
        return category._opposition_count


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ("name", "opposition", "slug", "question_count")
    list_display_links = ("name",)
    list_filter = ("opposition",)
    list_select_related = ("opposition",)
    list_per_page = 25
    search_fields = ("name", "slug", "opposition__name", "opposition__slug")
    ordering = ("opposition__name", "name")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(PracticePreset)
class PracticePresetAdmin(admin.ModelAdmin):
    list_display = (
        "opposition",
        "mode",
        "question_count",
        "duration_minutes",
        "mock_number",
        "mock_id",
    )
    list_filter = ("mode", "opposition")
    list_select_related = ("opposition",)
    list_per_page = 25
    search_fields = ("opposition__name", "opposition__slug", "mock_id")
    ordering = ("opposition__name", "mode", "mock_number")


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("statement", "topic", "slug")
    list_filter = ("topic__opposition",)
    list_select_related = ("topic", "topic__opposition")
    list_per_page = 25
    search_fields = ("statement", "topic__name", "topic__opposition__name")
    ordering = ("topic__opposition__name", "topic__name", "id")


@admin.register(QuestionReport)
class QuestionReportAdmin(admin.ModelAdmin):
    list_display = ("question", "reason", "status", "created_at")
    list_filter = ("status", "reason", "question__topic__opposition")
    list_select_related = ("question", "question__topic", "question__topic__opposition")
    list_per_page = 25
    search_fields = ("question__statement", "details")
    ordering = ("-created_at",)


admin.site.site_header = "OposNavarra · Administración"
admin.site.site_title = "Administración de OposNavarra"
admin.site.index_title = "Gestión del catálogo"
admin.site.empty_value_display = "—"
