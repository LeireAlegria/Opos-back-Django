from django.core.management.base import BaseCommand

from catalog.demo_question_bank import DEMO_QUESTIONS
from catalog.models import Category, Opposition, PracticePreset, Question, Topic


OPPOSITIONS = [
    ("auxiliar-administrativo", "Auxiliar Administrativo", "Administración", "📋", "#4f69d8", 2450),
    ("administrativo", "Administrativo del Estado", "Administración", "🏛️", "#263b78", 1830),
    ("policia-foral", "Policía Foral", "Seguridad", "🚔", "#a24f75", 1860),
    ("servicios-generales", "Servicios Generales", "Servicios", "🧰", "#7350da", 1620),
    ("celador", "Celador", "Sanidad", "🏥", "#397fa5", 1730),
    ("tcae", "TCAE", "Sanidad", "🩺", "#2a8a78", 2680),
    ("bombero", "Bombero", "Seguridad", "🧑‍🚒", "#d95b45", 2340),
    ("policia-municipal", "Policía Municipal", "Seguridad", "👮", "#3f779c", 1950),
    ("conserje", "Conserje", "Servicios", "🔑", "#df7b38", 1480),
    ("guarda-medio-ambiente", "Guarda Medio Ambiente", "Medio Ambiente", "🌲", "#5a9872", 1760),
]

DETAILS = {
    "auxiliar-administrativo": {
        "description": (
            "Prepara la oposición de Auxiliar Administrativo con preguntas sobre "
            "organización, gestión documental y atención al público."
        ),
        "topics": [
            ("organizacion-administrativa", "Organización administrativa", 280),
            ("gestion-documental", "Gestión documental y archivo", 260),
            ("atencion-ciudadano", "Atención al ciudadano", 240),
        ],
    },
    "administrativo": {
        "description": (
            "Prepara la oposición de Administrativo con preguntas organizadas por "
            "materias, práctica progresiva y simulacros para medir tu preparación."
        ),
        "topics": [
            ("constitucion", "Constitución Española", 310),
            ("organizacion-del-estado", "Organización del Estado", 245),
            ("procedimiento-administrativo", "Procedimiento administrativo común", 420),
            ("regimen-juridico", "Régimen jurídico del sector público", 285),
            ("empleo-publico", "Empleo público", 310),
            ("gestion-financiera", "Gestión financiera y presupuestaria", 260),
        ],
    },
    "celador": {
        "description": (
            "Repasa las funciones del celador, la atención a pacientes y la "
            "organización sanitaria con preguntas por temas y exámenes de práctica."
        ),
        "topics": [
            ("sistema-sanitario", "Organización del sistema sanitario", 250),
            ("derechos-pacientes", "Derechos y deberes de los pacientes", 180),
            ("funciones-celador", "Funciones del celador", 390),
            ("atencion-paciente", "Atención y acompañamiento al paciente", 340),
            ("movilizacion", "Movilización y traslado de pacientes", 310),
            ("higiene-seguridad", "Higiene, seguridad y prevención", 260),
            ("control-accesos", "Control de accesos y vigilancia", 220),
            ("evacuacion-urgencias", "Evacuación y actuaciones de urgencia", 210),
            ("primeros-auxilios", "Primeros auxilios básicos", 190),
        ],
    },
}


class Command(BaseCommand):
    help = "Carga en la base de datos el catálogo de demostración del frontend."

    def handle(self, *args, **options):
        for slug, name, category_name, icon, color, count in OPPOSITIONS:
            category_slug = {
                "Administración": "administracion",
                "Medio Ambiente": "medio-ambiente",
            }.get(category_name, category_name.lower())
            category, _ = Category.objects.update_or_create(
                slug=category_slug, defaults={"name": category_name}
            )
            description = DETAILS.get(slug, {}).get("description", "")
            opposition, _ = Opposition.objects.update_or_create(
                slug=slug,
                defaults={
                    "category": category,
                    "name": name,
                    "icon": icon,
                    "color": color,
                    "description": description,
                    "question_count": count,
                    "is_active": True,
                },
            )
            if slug not in DETAILS:
                continue

            details = DETAILS[slug]
            topic_slugs = []
            for topic_slug, topic_name, question_count in details["topics"]:
                topic_slugs.append(topic_slug)
                topic, _ = Topic.objects.update_or_create(
                    opposition=opposition,
                    slug=topic_slug,
                    defaults={
                        "name": topic_name,
                        "question_count": question_count,
                        "concepts": [],
                    },
                )
                for question_number, question_data in enumerate(
                    DEMO_QUESTIONS.get(slug, {}).get(topic_slug, []), start=1
                ):
                    statement, correct_answer, *distractors = question_data
                    choices = [correct_answer, *distractors]
                    rotation = (question_number - 1) % len(choices)
                    choices = choices[rotation:] + choices[:rotation]
                    options = [
                        {"id": chr(ord("a") + index), "text": text}
                        for index, text in enumerate(choices)
                    ]
                    correct_option = chr(ord("a") + choices.index(correct_answer))
                    Question.objects.update_or_create(
                        topic=topic,
                        slug=f"demo-{question_number:03}",
                        defaults={
                            "statement": statement,
                            "options": options,
                            "correct_option": correct_option,
                        },
                    )
            opposition.topics.exclude(slug__in=topic_slugs).delete()

            PracticePreset.objects.filter(opposition=opposition).delete()
            for mode in ("easy", "difficult"):
                PracticePreset.objects.create(
                    opposition=opposition,
                    mode=mode,
                    question_count=20,
                    duration_minutes=20,
                )
            for mock_number in range(1, 6):
                PracticePreset.objects.create(
                    opposition=opposition,
                    mode="full",
                    question_count=100,
                    duration_minutes=90,
                    mock_number=mock_number,
                    mock_id=f"mock-{mock_number}",
                )

        self.stdout.write(
            self.style.SUCCESS(
                "Catálogo de demostración cargado. Revisa y sustituye los datos antes de producción."
            )
        )
