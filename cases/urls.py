from django.urls import path

from cases import views
from correspondence import views as correspondence_views

urlpatterns = [
    path("", views.case_list, name="case-list"),
    path("new/", views.case_create, name="case-create"),
    path("<int:pk>/", views.case_detail, name="case-detail"),
    path("<int:pk>/edit/", views.case_update, name="case-update"),
    path("<int:pk>/transition/", views.case_transition, name="case-transition"),
    path("<int:pk>/extend/", views.case_extend, name="case-extend"),
    path("<int:pk>/note/", views.case_note, name="case-note"),
    path("<int:pk>/tasks/new/", views.task_create, name="task-create"),
    path("<int:pk>/tasks/<int:task_pk>/toggle/", views.task_toggle, name="task-toggle"),
    path("<int:pk>/checklist/toggle/", views.checklist_toggle, name="checklist-toggle"),
    path("<int:pk>/compose/", correspondence_views.compose, name="case-compose"),
    path("<int:pk>/reply/", correspondence_views.reply, name="case-reply"),
    path(
        "<int:pk>/attachments/upload/",
        correspondence_views.attachment_upload,
        name="case-attachment-upload",
    ),
    path(
        "<int:pk>/messages/<int:message_pk>/",
        correspondence_views.message_detail,
        name="message-detail",
    ),
    path(
        "<int:pk>/messages/<int:message_pk>/send/",
        correspondence_views.message_send,
        name="message-send",
    ),
    path(
        "<int:pk>/messages/<int:message_pk>/pdf/",
        correspondence_views.message_pdf,
        name="message-pdf",
    ),
    path(
        "<int:pk>/messages/<int:message_pk>/eml/",
        correspondence_views.message_eml,
        name="message-eml",
    ),
    path(
        "<int:pk>/messages/<int:message_pk>/print/",
        correspondence_views.message_print,
        name="message-print",
    ),
    path(
        "<int:pk>/messages/<int:message_pk>/delete/",
        correspondence_views.message_delete,
        name="message-delete",
    ),
]
