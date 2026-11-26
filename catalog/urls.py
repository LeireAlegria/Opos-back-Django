from django.urls import path

from . import views


urlpatterns = [
    path("csrf", views.csrf_token, name="csrf-token"),
    path("auth/magic/request", views.request_magic_link, name="magic-link-request"),
    path("auth/magic/verify/<str:token>", views.verify_magic_link, name="magic-link-verify"),
    path("auth/session", views.auth_session, name="auth-session"),
    path("auth/logout", views.auth_logout, name="auth-logout"),
    path("auth/settings/profile", views.update_profile_settings, name="update-profile-settings"),
    path("auth/settings/timezone", views.update_timezone_setting, name="update-timezone-setting"),
    path("oppositions", views.opposition_list, name="opposition-list"),
    path("oppositions/<slug:slug>", views.opposition_detail, name="opposition-detail"),
    path(
        "oppositions/<slug:opposition_slug>/topics/<slug:topic_slug>/questions",
        views.topic_questions,
        name="topic-questions",
    ),
    path(
        "oppositions/<slug:opposition_slug>/topics/<slug:topic_slug>/questions/<slug:question_slug>/reports",
        views.report_question,
        name="question-report",
    ),
]
