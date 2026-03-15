import math
from django.utils import timezone
from django.db import transaction

from accounts.models import CompanyTransaction, UserCreditTransaction
from messaging.models import Message


SMS_PRICE = 19  # Prix d'un SMS


def send_sms(user, phone, text, message_type='simple', campaign=None, scheduled_at=None):

    company = user.company

    if not company:
        return {"success": False, "error": "Aucune entreprise associée."}

    # 🔢 Calcul nombre de SMS (160 caractères par SMS)
    sms_parts = math.ceil(len(text) / 160)
    total_cost = sms_parts * SMS_PRICE

    # 💰 Vérification solde (uniquement si envoi immédiat)
    if not scheduled_at:
        if user.role == 'user':
            if user.credit_balance < total_cost:
                return {"success": False, "error": "Crédit utilisateur insuffisant."}
        else:
            if company.balance < total_cost:
                return {"success": False, "error": "Solde insuffisant."}

    # 🕐 Si planifié → on n’envoie pas maintenant
    if scheduled_at:
        Message.objects.create(
            user=user,
            company=company,
            campaign=campaign,
            phone=phone,
            message=text,
            message_type=message_type,
            status='scheduled',
            cost=total_cost,
            scheduled_at=scheduled_at
        )
        return {"success": True, "message": "Message planifié avec succès."}

    # ⚡ Envoi immédiat sécurisé (transaction DB)
    with transaction.atomic():

        # Création message
        Message.objects.create(
            user=user,
            company=company,
            campaign=campaign,
            phone=phone,
            message=text,
            message_type=message_type,
            status='sent',
            cost=total_cost,
            sent_at=timezone.now()
        )

        if user.role == 'user':
            user.credit_balance -= total_cost
            user.save(update_fields=['credit_balance'])

            UserCreditTransaction.objects.create(
                company=company,
                user=user,
                amount=total_cost,
                transaction_type='debit',
                description=f"SMS envoyé à {phone} ({sms_parts} SMS)"
            )
        else:
            company.balance -= total_cost
            company.save(update_fields=['balance'])

            CompanyTransaction.objects.create(
                company=company,
                amount=total_cost,
                transaction_type='debit',
                description=f"SMS envoyé à {phone} ({sms_parts} SMS)"
            )

    return {"success": True}