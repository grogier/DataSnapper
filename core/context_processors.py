from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.db.models import Q
from django.utils import timezone


def navigation(request):
    context = {
        "app_name": settings.APP_NAME,
        "app_version": settings.APP_VERSION,
        "app_tagline": settings.APP_TAGLINE,
        "nav_overdue": 0,
        "nav_due_soon": 0,
        "nav_open_cases": 0,
        "primary_profile": None,
    }
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return context

    from cases.models import Case
    from core.models import DataSubject

    today = timezone.localdate()
    open_statuses = [
        Case.Status.DRAFT,
        Case.Status.QUEUED,
        Case.Status.SENT,
        Case.Status.ACKNOWLEDGED,
        Case.Status.IDENTITY_CHECK,
        Case.Status.IN_PROGRESS,
        Case.Status.PARTIALLY_FULFILLED,
        Case.Status.REFUSED,
        Case.Status.NO_RESPONSE,
        Case.Status.ESCALATED,
    ]
    open_cases = Case.objects.filter(status__in=open_statuses)
    overdue = open_cases.filter(
        Q(due_at__lt=today, extended_due_at__isnull=True) | Q(extended_due_at__lt=today)
    ).count()
    due_soon = open_cases.filter(
        Q(due_at__gte=today, due_at__lte=today + timedelta(days=10))
        | Q(
            extended_due_at__gte=today,
            extended_due_at__lte=today + timedelta(days=10),
        )
    ).count()

    context.update(
        {
            "nav_overdue": overdue,
            "nav_due_soon": due_soon,
            "nav_open_cases": open_cases.count(),
            "primary_profile": DataSubject.get_primary(),
        }
    )
    return context
