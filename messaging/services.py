import math
from decimal import Decimal, ROUND_HALF_UP

from django.utils import timezone
from django.db import transaction

from accounts.models import CompanyTransaction, UserCreditTransaction
from messaging.models import Message

from django.contrib.auth import get_user_model
from accounts.models import Company


SMS_PRICE = 19


# =========================================================
# 🔢 CALCUL COUT
# =========================================================
def calculate_sms_cost(text):
    sms_parts = math.ceil(len(text) / 160)
    return sms_parts, sms_parts * SMS_PRICE


# =========================================================
# 🔢 FORMAT DECIMAL (FIX BUG)
# =========================================================
def to_decimal(value):
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


# =========================================================
# 📡 API SMS (RÉEL — ivoiresoftservices.net)
# =========================================================
def send_sms_api(phone, text, moteur=None, sender=None):
    from messaging.sms_gateway import send_sms
    return send_sms(phone, text, moteur=moteur, sender=sender)


def apply_billing(user, company, cost, phone, sms_parts):

    cost = to_decimal(cost)

    User = get_user_model()

    try:
        # ===============================
        # 👤 USER
        # ===============================
        if user.is_user():

            user = User.objects.select_for_update().get(id=user.id)

            current_balance = to_decimal(user.credit_balance)

            if current_balance < cost:
                return {"success": False, "error": "Crédit insuffisant"}

            new_balance = to_decimal(current_balance - cost)

            # 🔥 UPDATE DB DIRECT
            User.objects.filter(id=user.id).update(
                credit_balance=new_balance
            )

            # 🔥 RELOAD OBJECT (IMPORTANT)
            user.refresh_from_db()

            UserCreditTransaction.objects.create(
                company=company,
                user=user,
                amount=cost,
                transaction_type='debit',
                description=f"SMS envoyé à {phone} ({sms_parts} SMS)"
            )

        # ===============================
        # 🏢 ADMIN
        # ===============================
        elif user.is_admin():

            company = Company.objects.select_for_update().get(id=company.id)

            current_balance = to_decimal(company.balance)

            if current_balance < cost:
                return {"success": False, "error": "Solde insuffisant"}

            new_balance = to_decimal(current_balance - cost)

            Company.objects.filter(id=company.id).update(
                balance=new_balance
            )

            company.refresh_from_db()

            CompanyTransaction.objects.create(
                company=company,
                amount=cost,
                transaction_type='debit',
                description=f"SMS envoyé à {phone} ({sms_parts} SMS)"
            )

        else:
            return {"success": False, "error": "Rôle invalide"}

        return {"success": True}

    except Exception as e:
        return {"success": False, "error": str(e)}


# =========================================================
# 🚀 ENVOI IMMÉDIAT
# =========================================================

'''
def send_sms_now(user, phone, text, message_type='simple', campaign=None):

    company = user.company

    if not company:
        return {"success": False, "error": "Aucune entreprise associée."}

    sms_parts, total_cost = calculate_sms_cost(text)

    with transaction.atomic():

        billing = apply_billing(user, company, total_cost, phone, sms_parts)

        if not billing["success"]:
            return billing

        result = send_sms_api(phone, text)

        if not result["success"]:
            return result

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

    return {"success": True}
'''

def send_sms_now(user, phone, text, message_type='simple', title=None, campaign=None, moteur=None, sender=None):

    company = user.company

    if not company:
        return {"success": False, "error": "Aucune entreprise associée."}

    title = title or "SMS sans titre"
    sms_parts, total_cost = calculate_sms_cost(text)

    with transaction.atomic():

        billing = apply_billing(user, company, total_cost, phone, sms_parts)

        if not billing["success"]:
            return billing

        result = send_sms_api(phone, text, moteur=moteur, sender=sender)

        if not result["success"]:
            transaction.set_rollback(True)
            return result

        Message.objects.create(
            user=user,
            company=company,
            campaign=campaign,
            title=title,  # 🔥 AJOUT
            phone=phone,
            message=text,
            message_type=message_type,
            status='sent',
            cost=total_cost,
            sent_at=timezone.now()
        )

    return {"success": True}


def queue_sms_send(user, phone, text, message_type='simple', title=None, campaign=None, moteur=None, sender=None):
    company = user.company

    if not company:
        return {"success": False, "error": "Aucune entreprise associée."}

    title = title or "SMS sans titre"
    _sms_parts, total_cost = calculate_sms_cost(text)

    msg = Message.objects.create(
        user=user,
        company=company,
        campaign=campaign,
        title=title,
        phone=phone,
        message=text,
        message_type=message_type,
        status='pending',
        cost=total_cost,
    )

    def enqueue():
        from messaging.tasks import send_message_task
        send_message_task.delay(msg.id, moteur=moteur, sender=sender)

    transaction.on_commit(enqueue)

    return {"success": True, "queued": True, "message": msg}

# =========================================================
# 🕐 PLANIFICATION
# =========================================================
'''
def schedule_sms(user, phone, text, scheduled_at, message_type='simple', campaign=None):

    company = user.company

    if not company:
        return {"success": False, "error": "Aucune entreprise associée."}

    sms_parts, total_cost = calculate_sms_cost(text)

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

    return {"success": True}
'''

def schedule_sms(user, phone, text, scheduled_at, message_type='simple', title=None, campaign=None):

    company = user.company

    if not company:
        return {"success": False, "error": "Aucune entreprise associée."}

    title = title or "SMS sans titre"
    sms_parts, total_cost = calculate_sms_cost(text)

    Message.objects.create(
        user=user,
        company=company,
        campaign=campaign,
        title=title,  # 🔥 AJOUT
        phone=phone,
        message=text,
        message_type=message_type,
        status='scheduled',
        cost=total_cost,
        scheduled_at=scheduled_at
    )

    return {"success": True}
