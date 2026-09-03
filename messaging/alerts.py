import logging

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from accounts.models import User
from messaging.models import Message

logger = logging.getLogger(__name__)


def send_sms_failure_alert(message_id, reason):
    if not getattr(settings, "SMS_FAILURE_ALERTS_ENABLED", True):
        return {"sent": 0, "skipped": True}

    try:
        msg = Message.objects.select_related("company", "user", "campaign").get(pk=message_id)
    except Message.DoesNotExist:
        logger.warning("SMS failure alert skipped: message %s not found", message_id)
        return {"sent": 0, "skipped": True}

    recipients = list(
        User.objects.filter(
            company=msg.company,
            role="admin",
            is_active=True,
        )
        .exclude(email="")
        .values_list("email", flat=True)
        .distinct()
    )

    if not recipients:
        logger.warning(
            "SMS failure alert skipped: no admin email for company=%s message=%s",
            msg.company_id,
            msg.id,
        )
        return {"sent": 0, "skipped": True}

    reason = str(reason or msg.failure_reason or "Erreur inconnue")[:2000]
    subject = f"[ISS SMS] Probleme d'envoi SMS - {msg.company.name}"
    last_attempt = msg.last_attempt_at or timezone.now()

    body = "\n".join([
        "Bonjour,",
        "",
        "Un probleme d'envoi SMS a ete detecte sur la plateforme ISS SMS.",
        "",
        f"Entreprise : {msg.company.name}",
        f"Utilisateur : {msg.user.get_full_name() or msg.user.username}",
        f"Message ID : {msg.id}",
        f"Type : {msg.message_type}",
        f"Titre : {msg.title}",
        f"Campagne : {msg.campaign.name if msg.campaign else '-'}",
        f"Expediteur : {msg.sender_name or '-'}",
        f"Telephone : {msg.phone}",
        f"Statut : {msg.status}",
        f"Tentatives : {msg.attempt_count}",
        f"Derniere tentative : {last_attempt.strftime('%Y-%m-%d %H:%M:%S %Z')}",
        "",
        "Detail de l'erreur :",
        reason,
        "",
        "Action conseillee : verifier le dashboard ISS SMS, le solde, le sender,",
        "les numeros concernes et l'etat du fournisseur SMS.",
        "",
        "Ceci est une alerte automatique.",
    ])

    try:
        sent = send_mail(
            subject,
            body,
            settings.DEFAULT_FROM_EMAIL,
            recipients,
            fail_silently=False,
        )
    except Exception as exc:
        logger.error("SMS failure alert email failed message=%s -> %s", msg.id, exc)
        return {"sent": 0, "error": str(exc)}

    logger.info("SMS failure alert sent message=%s recipients=%s", msg.id, sent)
    return {"sent": sent, "recipients": recipients}
