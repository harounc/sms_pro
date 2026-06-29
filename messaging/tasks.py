import logging

from celery.exceptions import MaxRetriesExceededError
from celery import shared_task
from django.db import transaction
from django.utils import timezone

from messaging.models import Message
from messaging.services import apply_billing, calculate_sms_cost, send_sms_api

logger = logging.getLogger(__name__)


def _should_retry(error):
    if not error:
        return False
    retry_markers = ("HTTP 500", "HTTP 502", "HTTP 503", "HTTP 504", "timeout", "temporarily")
    return any(marker.lower() in str(error).lower() for marker in retry_markers)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_message_task(self, message_id, moteur=None, sender=None):
    api_failed = False
    api_error = None

    try:
        with transaction.atomic():
            msg = Message.objects.select_for_update().select_related("user", "company").get(pk=message_id)

            if msg.status not in {"pending", "scheduled"}:
                return {"success": True, "skipped": True, "status": msg.status}

            sms_parts, _total_cost = calculate_sms_cost(msg.message)

            billing = apply_billing(
                user=msg.user,
                company=msg.company,
                cost=msg.cost,
                phone=msg.phone,
                sms_parts=sms_parts,
            )

            if not billing.get("success"):
                msg.status = "failed"
                msg.save(update_fields=["status"])
                return {"success": False, "error": billing.get("error")}

            result = send_sms_api(msg.phone, msg.message, moteur=moteur, sender=sender)

            if not result.get("success"):
                api_failed = True
                api_error = result.get("error", "Erreur API gateway")
                transaction.set_rollback(True)
            else:
                msg.status = "sent"
                msg.sent_at = timezone.now()
                msg.save(update_fields=["status", "sent_at"])

        if api_failed:
            if _should_retry(api_error):
                raise self.retry(exc=RuntimeError(api_error))

            Message.objects.filter(pk=message_id).update(status="failed")
            logger.error("SMS FAIL message=%s -> %s", message_id, api_error)
            return {"success": False, "error": api_error}

        return {"success": True}

    except MaxRetriesExceededError:
        Message.objects.filter(pk=message_id).update(status="failed")
        logger.error("SMS FAIL message=%s -> retries exceeded", message_id)
        return {"success": False, "error": "Retries exceeded"}


@shared_task
def enqueue_due_scheduled_messages(limit=500):
    now = timezone.now()
    ids = list(
        Message.objects.filter(status="scheduled", scheduled_at__lte=now)
        .order_by("scheduled_at")
        .values_list("id", flat=True)[:limit]
    )

    for message_id in ids:
        Message.objects.filter(id=message_id, status="scheduled").update(status="pending")
        send_message_task.delay(message_id)

    return {"queued": len(ids)}
