import json

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from .models import (
    Category,
    MagicLink,
    Opposition,
    PracticePreset,
    Question,
    QuestionReport,
    Topic,
    UserSettings,
)


class MagicLinkAuthTests(TestCase):
    def test_register_request_creates_user_and_one_time_link(self):
        response = self.client.post(
            reverse("magic-link-request"),
            data=json.dumps({
                "purpose": "register",
                "email": "opositora@example.com",
                "firstName": "Ana",
                "firstSurname": "López",
                "secondSurname": "Ruiz",
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        User = get_user_model()
        user = User.objects.get(email="opositora@example.com")
        self.assertEqual(user.first_name, "Ana")
        self.assertEqual(user.last_name, "López Ruiz")
        self.assertEqual(MagicLink.objects.filter(user=user).count(), 1)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_verify_logs_user_in_and_rejects_second_use(self):
        User = get_user_model()
        user = User.objects.create_user(
            username="ana@example.com",
            email="ana@example.com",
            first_name="Ana",
        )
        token, magic_link = MagicLink.create_for(user, "login")

        response = self.client.get(
            reverse("magic-link-verify", kwargs={"token": token}),
        )
        self.assertEqual(response.status_code, 302)
        session_response = self.client.get(reverse("auth-session"))
        self.assertTrue(session_response.json()["authenticated"])

        second_response = self.client.get(
            reverse("magic-link-verify", kwargs={"token": token}),
        )
        self.assertIn("auth=invalid", second_response["Location"])

    def test_profile_name_can_be_changed_only_once(self):
        user = get_user_model().objects.create_user(
            username="profile@example.com",
            email="profile@example.com",
            first_name="Ana",
            last_name="López",
        )
        self.client.force_login(user)

        response = self.client.post(
            reverse("update-profile-settings"),
            data=json.dumps({"firstName": "María", "lastName": "García"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        user.refresh_from_db()
        self.assertEqual(user.first_name, "María")
        self.assertTrue(UserSettings.objects.get(user=user).name_changed)

        second_response = self.client.post(
            reverse("update-profile-settings"),
            data=json.dumps({"firstName": "Otra", "lastName": "Persona"}),
            content_type="application/json",
        )
        self.assertEqual(second_response.status_code, 409)

    def test_timezone_setting_is_saved_for_authenticated_user(self):
        user = get_user_model().objects.create_user(
            username="timezone@example.com",
            email="timezone@example.com",
        )
        self.client.force_login(user)

        response = self.client.post(
            reverse("update-timezone-setting"),
            data=json.dumps({"timezone": "Europe/Madrid"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(UserSettings.objects.get(user=user).timezone, "Europe/Madrid")

    def test_logout_ends_authenticated_session(self):
        user = get_user_model().objects.create_user(
            username="logout@example.com",
            email="logout@example.com",
        )
        self.client.force_login(user)

        response = self.client.post(reverse("auth-logout"))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.client.get(reverse("auth-session")).json()["authenticated"])


class OppositionApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = Category.objects.create(name="Sanidad", slug="sanidad")
        cls.opposition = Opposition.objects.create(
            category=cls.category,
            slug="celador",
            name="Celador",
            icon="🏥",
            color="#397fa5",
            description="Ficha de demostración.",
            question_count=1730,
        )
        Topic.objects.create(
            opposition=cls.opposition,
            slug="movilizacion",
            name="Movilización",
            question_count=310,
        )
        PracticePreset.objects.create(
            opposition=cls.opposition,
            mode=PracticePreset.Mode.EASY,
            question_count=20,
            duration_minutes=20,
        )
        PracticePreset.objects.create(
            opposition=cls.opposition,
            mode=PracticePreset.Mode.FULL,
            question_count=100,
            duration_minutes=90,
            mock_number=1,
            mock_id="mock-1",
        )

    def test_list_returns_paginated_items_and_filters(self):
        response = self.client.get("/api/oppositions", {"category": "Sanidad"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["totalItems"], 1)
        self.assertEqual(response.json()["items"][0]["slug"], "celador")

    def test_list_rejects_invalid_page_size(self):
        response = self.client.get("/api/oppositions", {"pageSize": 0})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "invalid_page_size")

    def test_detail_returns_topics_and_practice_configuration(self):
        response = self.client.get("/api/oppositions/celador")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["topics"][0]["slug"], "movilizacion")
        self.assertEqual(payload["practice"]["easy"]["questionCount"], 20)
        self.assertEqual(payload["practice"]["fullMocks"][0]["id"], "mock-1")
        self.assertIsNone(payload["contentReviewedAt"])

    def test_detail_returns_not_found_for_unknown_slug(self):
        response = self.client.get("/api/oppositions/no-existe")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "not_found")

    def test_topic_questions_returns_five_questions_without_answers(self):
        topic = self.opposition.topics.get(slug="movilizacion")
        for number in range(5):
            Question.objects.create(
                topic=topic,
                slug=f"pregunta-{number}",
                statement=f"Pregunta de prueba {number}",
                options=[{"id": "a", "text": "Opción"}],
                correct_option="a",
            )

        response = self.client.get(
            "/api/oppositions/celador/topics/movilizacion/questions"
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["questionCount"], 5)
        self.assertEqual(payload["durationMinutes"], 5)
        self.assertEqual(len(payload["questions"]), 5)
        self.assertNotIn("correct_option", payload["questions"][0])
        self.assertNotIn("correctOption", payload["questions"][0])

    def test_topic_questions_reports_when_topic_has_fewer_than_five(self):
        response = self.client.get(
            "/api/oppositions/celador/topics/movilizacion/questions"
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.json()["error"]["code"], "insufficient_questions"
        )

    def test_question_report_is_saved_with_csrf_protection(self):
        topic = self.opposition.topics.get(slug="movilizacion")
        question = Question.objects.create(
            topic=topic,
            slug="pregunta-reportable",
            statement="Pregunta de ejemplo",
            options=[{"id": "a", "text": "Opción"}],
            correct_option="a",
        )
        client = Client(enforce_csrf_checks=True)
        csrf_response = client.get("/api/csrf", HTTP_HOST="localhost")
        csrf_token = csrf_response.json()["csrfToken"]

        response = client.post(
            reverse(
                "question-report",
                kwargs={
                    "opposition_slug": "celador",
                    "topic_slug": "movilizacion",
                    "question_slug": question.slug,
                },
            ),
            data=json.dumps({"reason": "unclear", "details": "El enunciado no se entiende."}),
            content_type="application/json",
            HTTP_HOST="localhost",
            HTTP_ORIGIN="http://localhost:5173",
            HTTP_X_CSRFTOKEN=csrf_token,
        )

        self.assertEqual(response.status_code, 201)
        report = QuestionReport.objects.get(question=question)
        self.assertEqual(report.reason, QuestionReport.Reason.UNCLEAR)
        self.assertEqual(report.details, "El enunciado no se entiende.")

    def test_question_report_rejects_invalid_reason(self):
        topic = self.opposition.topics.get(slug="movilizacion")
        question = Question.objects.create(
            topic=topic,
            slug="pregunta-reportable",
            statement="Pregunta de ejemplo",
            options=[{"id": "a", "text": "Opción"}],
            correct_option="a",
        )

        response = self.client.post(
            reverse(
                "question-report",
                kwargs={
                    "opposition_slug": "celador",
                    "topic_slug": "movilizacion",
                    "question_slug": question.slug,
                },
            ),
            data=json.dumps({"reason": "not-a-reason", "details": ""}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "invalid_reason")


class AdminBrandingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin_user = get_user_model().objects.create_superuser(
            username="catalog-admin",
            email="admin@example.com",
            password="test-password-for-admin",
        )

    def test_admin_home_uses_custom_branding_and_stylesheet(self):
        self.client.force_login(self.admin_user)

        response = self.client.get("/admin/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "OposNavarra")
        self.assertContains(response, "catalog/admin.css")
        self.assertContains(response, "Temas")
        self.assertContains(response, "Modalidades de práctica")
