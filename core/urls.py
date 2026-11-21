from django.urls import path

from core import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("settings/", views.settings_view, name="settings"),
    path("settings/llm/test/", views.settings_llm_test, name="settings-llm-test"),
    path("search/", views.search_view, name="search"),
    path("calendar/", views.calendar_view, name="calendar"),
    path("calendar.ics", views.calendar_ics, name="calendar-ics"),
]
