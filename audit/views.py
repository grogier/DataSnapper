from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render

from audit.models import AuditLog
from audit.services import verify_chain


@login_required
def audit_list(request):
    entries = AuditLog.objects.select_related("actor")
    query = request.GET.get("q", "").strip()
    action = request.GET.get("action", "")
    if query:
        entries = entries.filter(
            Q(summary__icontains=query)
            | Q(entity_type__icontains=query)
            | Q(entity_id__icontains=query)
            | Q(actor__username__icontains=query)
        )
    if action:
        entries = entries.filter(action=action)

    actions = AuditLog.objects.order_by("action").values_list("action", flat=True).distinct()
    paginator = Paginator(entries, 50)
    page = paginator.get_page(request.GET.get("page"))
    chain_ok, bad_id = verify_chain()
    return render(
        request,
        "audit/list.html",
        {
            "page": page,
            "entries": page.object_list,
            "query": query,
            "action": action,
            "actions": actions,
            "chain_ok": chain_ok,
            "bad_id": bad_id,
            "total": paginator.count,
        },
    )
