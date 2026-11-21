from django.urls import path

from correspondence import views

urlpatterns = [
    path("", views.template_list, name="template-list"),
    path("new/", views.template_create, name="template-create"),
    path("<int:pk>/", views.template_detail, name="template-detail"),
    path("<int:pk>/edit/", views.template_edit, name="template-edit"),
]
