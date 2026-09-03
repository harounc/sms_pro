from datetime import timedelta

from celery import current_app
from django.utils import timezone

from messaging.models import Message


def get_sms_runtime_status(messages_qs=None, include_celery=True):
    now = timezone.now()
    qs = messages_qs if messages_qs is not None else Message.objects.all()

    pending_qs = qs.filter(status="pending")
    pending_count = pending_qs.count()
    oldest_pending = pending_qs.order_by("created_at").first()

    due_scheduled_count = qs.filter(
        status="scheduled",
        scheduled_at__lte=now,
    ).count()

    failed_today_count = qs.filter(
        status="failed",
        created_at__date=now.date(),
    ).count()

    sent_today_count = qs.filter(
        status="sent",
        sent_at__date=now.date(),
    ).count()

    oldest_pending_age_minutes = None
    if oldest_pending:
        age = now - oldest_pending.created_at
        oldest_pending_age_minutes = max(0, int(age.total_seconds() // 60))

    celery_ok = None
    celery_workers = 0
    if include_celery:
        try:
            inspector = current_app.control.inspect(timeout=0.5)
            pings = inspector.ping() or {}
        except Exception:
            pings = {}
        celery_workers = len(pings)
        celery_ok = celery_workers > 0

    has_warning = (
        pending_count > 100
        or due_scheduled_count > 0
        or (
            oldest_pending
            and oldest_pending.created_at < now - timedelta(minutes=10)
        )
        or celery_ok is False
    )

    return {
        "ok": not has_warning,
        "celery_ok": celery_ok,
        "celery_workers": celery_workers,
        "pending_count": pending_count,
        "oldest_pending_age_minutes": oldest_pending_age_minutes,
        "due_scheduled_count": due_scheduled_count,
        "failed_today_count": failed_today_count,
        "sent_today_count": sent_today_count,
        "checked_at": now,
    }
