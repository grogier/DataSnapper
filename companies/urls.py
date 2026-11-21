from django.urls import path

from companies import views

urlpatterns = [
    path("", views.organization_list, name="organization-list"),
    path("new/", views.organization_create, name="organization-create"),
    path("<int:pk>/", views.organization_detail, name="organization-detail"),
    path("<int:pk>/edit/", views.organization_update, name="organization-update"),
    path("<int:pk>/delete/", views.organization_delete, name="organization-delete"),
    path("<int:pk>/contacts/new/", views.contact_create, name="contact-create"),
    path(
        "<int:pk>/contacts/<int:contact_pk>/edit/",
        views.contact_update,
        name="contact-update",
    ),
    path(
        "<int:pk>/contacts/<int:contact_pk>/delete/",
        views.contact_delete,
        name="contact-delete",
    ),
    path("<int:pk>/inventory/new/", views.inventory_create, name="inventory-create"),
    path(
        "<int:pk>/inventory/<int:entry_pk>/delete/",
        views.inventory_delete,
        name="inventory-delete",
    ),
]
