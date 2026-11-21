from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_not_required
from django.urls import include, path

from core import views as core_views

admin.site.site_header = "DataSnapper administration"
admin.site.site_title = "DataSnapper"
admin.site.index_title = "Data"

urlpatterns = [
    path("admin/", admin.site.urls),
    path(
        "accounts/login/",
        login_not_required(auth_views.LoginView.as_view(template_name="registration/login.html")),
        name="login",
    ),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("healthz", core_views.health, name="health"),
    path("", include("core.urls")),
    path("companies/", include("companies.urls")),
    path("cases/", include("cases.urls")),
    path("templates/", include("correspondence.urls")),
    path("evidence/", include("correspondence.evidence_urls")),
    path("audit/", include("audit.urls")),
]
