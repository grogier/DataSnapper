from django.urls import path

from correspondence import views

urlpatterns = [
    path("", views.evidence_list, name="evidence-list"),
    path("upload/", views.evidence_upload, name="evidence-upload"),
    path("<int:pk>/download/", views.attachment_download, name="attachment-download"),
    path("<int:pk>/delete/", views.attachment_delete, name="attachment-delete"),
]
