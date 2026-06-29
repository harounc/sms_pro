import re
import csv
import json
import os
import logging
import pandas as pd

from datetime import timedelta
from decimal import Decimal

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, HttpResponse, JsonResponse
from django.utils.dateparse import parse_datetime
from django.db.models import Sum, Count, Q
from django.utils import timezone
from django.core.paginator import Paginator
from django.contrib import messages

from messaging.services import queue_sms_send, schedule_sms
from messaging.models import Message, Campaign, Sender
from messaging.sms_gateway import validate_sms_configuration
from accounts.models import Company, User
from contacts.models import ContactGroup
from accounts.forms import RechargeForm

from django.db.models.functions import TruncDate


# from billing.models import Recharge  # ⚠️ adapte si ton app diffère
logger = logging.getLogger(__name__)
PHONE_REGEX = re.compile(r"^\+225\d{10}$")
VALID_MOTEURS = {"ORANGE", "MTN", "MOOV"}

# =========================================================
# Coût d'un SMS
# =========================================================
SMS_PRICE = 19


# =========================================================
# UTILS
# =========================================================

def is_company_admin(user):
    return user.role == "admin" and user.company


def get_user_groups(user):
    if is_company_admin(user):
        return ContactGroup.objects.filter(company=user.company)
    return ContactGroup.objects.filter(company=user.company, owner=user)


def parse_scheduled_datetime(value):
    if not value:
        return None, None

    scheduled_at = parse_datetime(value)
    if not scheduled_at:
        return None, "Date de programmation invalide."

    if timezone.is_naive(scheduled_at):
        scheduled_at = timezone.make_aware(scheduled_at)

    if scheduled_at <= timezone.now():
        return None, "La date de programmation doit être dans le futur."

    return scheduled_at, None


def get_approved_sender(user, sender_id):
    if not sender_id or not user.company_id:
        return None

    return Sender.objects.filter(
        id=sender_id,
        company=user.company,
        status="approved",
    ).first()


# =========================================================
# ADMIN DASHBOARD
# =========================================================


@login_required
def admin_dashboard_view(request):

    if not request.user.is_super_admin():
        return render(request, "messaging/forbidden.html")

    today = timezone.now().date()
    last_7_days = today - timedelta(days=6)

    messages = Message.objects.all()

    # ==============================
    # KPI PRINCIPAUX
    # ==============================
    total_sms = messages.filter(status='sent').count()

    total_revenue = messages.filter(
        status='sent'
    ).aggregate(total=Sum('cost'))['total'] or 0

    total_companies = Company.objects.count()

    active_companies = Company.objects.filter(
        users__is_active=True
    ).distinct().count()

    total_users = User.objects.filter(is_active=True).count()

    total_balance = Company.objects.aggregate(
        total=Sum('balance')
    )['total'] or 0

    sms_today = messages.filter(
        sent_at__date=today,
        status='sent'
    ).count()

    # ==============================
    # TOP ENTREPRISES
    # ==============================
    top_companies = Company.objects.annotate(
        sms_count=Count('message')
    ).order_by('-sms_count')[:5]

    # ==============================
    # TOP USERS
    # ==============================
    top_users = User.objects.annotate(
        sms_count=Count('message')
    ).order_by('-sms_count')[:5]

    # ==============================
    # RECHARGEMENTS
    # ==============================
    #recent_recharges = Recharge.objects.select_related('company').order_by('-created_at')[:5]

    # ==============================
    # GRAPH SMS (7 jours)
    # ==============================
    daily_stats = (
        messages.filter(
            status='sent',
            sent_at__date__gte=last_7_days
        )
        .annotate(date=TruncDate('sent_at'))
        .values('date')
        .annotate(count=Count('id'))
        .order_by('date')
    )

    stats_dict = {x["date"]: x["count"] for x in daily_stats}

    daily_data = []

    for i in range(7):
        day = last_7_days + timedelta(days=i)
        daily_data.append({
            "date": day.strftime("%d/%m"),
            "count": stats_dict.get(day, 0)
        })

    # ==============================
    # CONSOMMATION PAR ENTREPRISE
    # ==============================
    company_usage = Company.objects.annotate(
        total_spent=Sum('message__cost')
    ).order_by('-total_spent')[:10]

    # ==============================
    # CONTEXT
    # ==============================
    context = {
        "total_sms": total_sms,
        "total_revenue": total_revenue,
        "total_companies": total_companies,
        "active_companies": active_companies,
        "total_users": total_users,
        "total_balance": total_balance,
        "sms_today": sms_today,
        "top_companies": top_companies,
        "top_users": top_users,
        #"recent_recharges": recent_recharges,
        "daily_data": json.dumps(daily_data),
        "company_usage": company_usage,
    }

    return render(request, "messaging/admin_dashboard.html", context)



#############################################################
# SMS SIMPLE (multi numéros + planification)
#############################################################


@login_required
def send_sms_view(request):

    contact_groups = get_user_groups(request.user)

    senders = Sender.objects.filter(
        company=request.user.company,
        status='approved'
    )

    if not senders.exists():
        return render(request, "messaging/send_sms.html", {
            "error": "Aucun expéditeur approuvé disponible. Veuillez contacter l'administrateur."
        })

    if request.method == "POST":

        numbers_input = request.POST.get("phone")
        message = request.POST.get("message")
        title = request.POST.get("title")
        name = request.POST.get("name", "")
        scheduled_input = request.POST.get("scheduled_at")
        moteur_input = request.POST.get("moteur") or None  # None = auto-routing API
        sender_id = request.POST.get("sender")

        # ===============================
        # ❌ VALIDATION
        # ===============================
        sender = get_approved_sender(request.user, sender_id)
        if not sender:
            return render(request, "messaging/send_sms.html", {
                "contact_groups": contact_groups,
                "senders": senders,
                "error": "Veuillez sélectionner un expéditeur approuvé."
            })

        if not numbers_input:
            return render(request, "messaging/send_sms.html", {
                "contact_groups": contact_groups,
                "senders": senders,
                "error": "Veuillez saisir au moins un numéro."
            })

        if not message:
            return render(request, "messaging/send_sms.html", {
                "contact_groups": contact_groups,
                "senders": senders,
                "error": "Le message est obligatoire."
            })

        if not title:
            return render(request, "messaging/send_sms.html", {
                "contact_groups": contact_groups,
                "senders": senders,
                "error": "Le titre est obligatoire."
            })

        if moteur_input and moteur_input not in VALID_MOTEURS:
            return render(request, "messaging/send_sms.html", {
                "contact_groups": contact_groups,
                "senders": senders,
                "error": "Opérateur invalide."
            })

        # ===============================
        # 🕐 PLANIFICATION
        # ===============================
        scheduled_at, scheduled_error = parse_scheduled_datetime(scheduled_input)
        if scheduled_error:
            return render(request, "messaging/send_sms.html", {
                "contact_groups": contact_groups,
                "senders": senders,
                "error": scheduled_error
            })

        numbers = [num.strip() for num in numbers_input.split(";") if num.strip()]

        if not scheduled_at:
            config_error = validate_sms_configuration(sender=sender.name)
            if config_error:
                messages.error(request, f"Configuration SMS incomplète : {config_error}")
                return redirect("dashboard")

        total_sent = 0
        invalid_numbers = []
        failed_numbers = []

        # ===============================
        # 🔁 TRAITEMENT NUMEROS
        # ===============================
        for phone in numbers:

            if not PHONE_REGEX.fullmatch(phone):
                invalid_numbers.append(phone)
                continue

            final_message = message.replace("{{name}}", name)

            if scheduled_at:
                result = schedule_sms(
                    user=request.user,
                    phone=phone,
                    text=final_message,
                    scheduled_at=scheduled_at,
                    message_type='simple',
                    title=title  # 🔥 IMPORTANT
                )
            else:
                result = queue_sms_send(
                    user=request.user,
                    phone=phone,
                    text=final_message,
                    message_type='simple',
                    title=title,
                    moteur=moteur_input,
                    sender=sender.name,
                )

            if result.get("success"):
                total_sent += 1
            else:
                error = result.get('error', 'erreur inconnue')
                logger.error("SMS FAIL %s → %s", phone, error)
                failed_numbers.append((phone, error))

        # ===============================
        # 🚨 NUMEROS INVALIDES (avertissement non bloquant)
        # ===============================
        if invalid_numbers and total_sent > 0:
            messages.warning(request, f"Numéros invalides ignorés : {', '.join(invalid_numbers)}")

        if total_sent == 0:
            if failed_numbers:
                last_error = failed_numbers[-1][1]
                messages.error(request, f"Aucun SMS envoyé. Motif : {last_error}")
            elif invalid_numbers:
                messages.error(request, f"Aucun SMS envoyé. Numéros invalides : {', '.join(invalid_numbers)}")
            else:
                messages.error(request, "Aucun SMS valide n'a pu être traité.")
        elif failed_numbers:
            failed_phones = ", ".join(phone for phone, _error in failed_numbers)
            messages.warning(request, f"Certains SMS n'ont pas été envoyés : {failed_phones}")
        elif scheduled_at:
            messages.success(request, f"{total_sent} SMS planifiés avec succès.")
        else:
            messages.success(request, f"{total_sent} SMS mis en file d'envoi.")

        return redirect("dashboard")

    return render(request, "messaging/send_sms.html", {
        "contact_groups": contact_groups,
        "senders": senders
    })


# =========================================================
# CAMPAIGN
# =========================================================




@login_required
def campaign_upload_view(request):

    contact_groups = get_user_groups(request.user)

    senders = Sender.objects.filter(
        company=request.user.company,
        status='approved'
    )

    rows_data = []

    def render_campaign_error(error):
        return render(request, "messaging/campaign_upload.html", {
            "contact_groups": contact_groups,
            "senders": senders,
            "error": error,
        })

    if request.method == "POST":

        file = request.FILES.get("file")
        message_text = request.POST.get("message")
        title = request.POST.get("title")
        group_id = request.POST.get("contact_group")
        sender_id = request.POST.get("sender")

        scheduled_at_str = request.POST.get("scheduled_at")
        scheduled_at, scheduled_error = parse_scheduled_datetime(scheduled_at_str)

        # ===============================
        # ❌ VALIDATIONS
        # ===============================
        if not message_text:
            return render_campaign_error("Le message est obligatoire.")

        if not title:
            return render_campaign_error("Le titre est obligatoire.")

        if not file and not group_id:
            return render_campaign_error("Veuillez choisir un fichier ou un groupe.")

        if file and group_id:
            return render_campaign_error("Veuillez choisir soit un fichier Excel, soit un groupe, pas les deux.")

        if scheduled_error:
            return render_campaign_error(scheduled_error)

        sender = get_approved_sender(request.user, sender_id)
        if not sender:
            return render_campaign_error("Veuillez sélectionner un expéditeur.")

        if not scheduled_at:
            config_error = validate_sms_configuration(sender=sender.name)
            if config_error:
                return render_campaign_error(f"Configuration SMS incomplète : {config_error}")

        df = None
        contacts = None

        if file:
            try:
                df = pd.read_excel(file, dtype=str)
            except Exception:
                return render_campaign_error("Erreur lecture fichier Excel.")

            if "phone" not in df.columns:
                return render_campaign_error("Colonne 'phone' obligatoire.")

        elif group_id:
            group = get_user_groups(request.user).filter(id=group_id).first()
            if not group:
                return render_campaign_error("Groupe de contacts invalide.")

            contacts = group.contacts.filter(company=request.user.company)
            if not is_company_admin(request.user):
                contacts = contacts.filter(user=request.user)

        # ===============================
        # 🎯 CRÉATION CAMPAGNE
        # ===============================
        campaign = Campaign.objects.create(
            user=request.user,
            company=request.user.company,
            name=title,
            message=message_text
        )

        total_sent = 0

        # ===============================
        # 📁 EXCEL
        # ===============================
        if file:

            for _, row in df.iterrows():

                phone = str(row.get("phone", "")).strip()
                name = str(row.get("name", "")).strip()

                # ❌ INVALID
                if not PHONE_REGEX.fullmatch(phone):
                    rows_data.append({
                        "phone": phone,
                        "status": "invalid"
                    })
                    continue

                final_message = message_text.replace("{{name}}", name)

                try:
                    if scheduled_at:
                        result = schedule_sms(
                            user=request.user,
                            phone=phone,
                            text=final_message,
                            scheduled_at=scheduled_at,
                            message_type='campaign',
                            campaign=campaign,
                            title=title
                        )
                    else:
                        result = queue_sms_send(
                            user=request.user,
                            phone=phone,
                            text=final_message,
                            message_type='campaign',
                            campaign=campaign,
                            title=title,
                            sender=sender.name,
                        )

                    if result.get("success"):
                        total_sent += 1
                        rows_data.append({
                            "phone": phone,
                            "status": "imported"
                        })
                    else:
                        rows_data.append({
                            "phone": phone,
                            "status": "error"
                        })

                except Exception:
                    logger.exception("Erreur traitement campagne Excel pour %s", phone)
                    rows_data.append({
                        "phone": phone,
                        "status": "error"
                    })

        # ===============================
        # 👥 GROUPE
        # ===============================
        elif group_id:

            for contact in contacts:

                phone = contact.phone
                name = contact.name or ""

                if not PHONE_REGEX.fullmatch(phone):
                    rows_data.append({
                        "phone": phone,
                        "status": "invalid"
                    })
                    continue

                final_message = message_text.replace("{{name}}", name)

                try:
                    if scheduled_at:
                        result = schedule_sms(
                            user=request.user,
                            phone=phone,
                            text=final_message,
                            scheduled_at=scheduled_at,
                            message_type='campaign',
                            campaign=campaign,
                            title=title
                        )
                    else:
                        result = queue_sms_send(
                            user=request.user,
                            phone=phone,
                            text=final_message,
                            message_type='campaign',
                            campaign=campaign,
                            title=title,
                            sender=sender.name,
                        )

                    if result.get("success"):
                        total_sent += 1
                        rows_data.append({
                            "phone": phone,
                            "status": "imported"
                        })
                    else:
                        rows_data.append({
                            "phone": phone,
                            "status": "error"
                        })

                except Exception:
                    logger.exception("Erreur traitement campagne groupe pour %s", phone)
                    rows_data.append({
                        "phone": phone,
                        "status": "error"
                    })

        # ===============================
        # 🎯 RESULTAT
        # ===============================
        if total_sent == 0:
            messages.warning(request, "Aucun SMS valide n’a été traité.")
        elif scheduled_at:
            messages.success(request, f"{total_sent} SMS programmés avec succès.")
        else:
            messages.success(request, f"{total_sent} SMS mis en file d'envoi.")

        return redirect("dashboard")


    return render(request, "messaging/campaign_upload.html", {
        "contact_groups": contact_groups,
        "senders": senders
    })


# =========================================================
# DASHBOARD ENTREPRISE Admin et users
# =========================================================

@login_required
def dashboard_view(request):

    # Rechargement depuis DB pour avoir balance/credit_balance à jour
    from accounts.models import User as UserModel, Company as CompanyModel
    user    = UserModel.objects.get(id=request.user.id)
    company = CompanyModel.objects.get(id=user.company_id) if user.company_id else None

    period = request.GET.get("period", "7")
    today = timezone.now().date()

    # ===============================
    # PERIODE
    # ===============================
    if period == "1":
        start_date = today
        days_range = 1
    elif period == "30":
        start_date = today - timedelta(days=29)
        days_range = 30
    else:
        start_date = today - timedelta(days=6)
        days_range = 7

    # ===============================
    # FILTRE PAR ROLE
    # ===============================
    if user.role == "admin":
        messages_qs = Message.objects.filter(company=company)
        balance = getattr(company, "balance", 0)
    else:
        messages_qs = Message.objects.filter(company=company, user=user)
        balance = getattr(user, "credit_balance", 0)

    # ===============================
    # STATISTIQUES
    # ===============================
    sent_messages = messages_qs.filter(
        status="sent",
        sent_at__date__gte=start_date
    )

    total_sms = sent_messages.count()

    total_spent = sent_messages.aggregate(
        total=Sum("cost")
    )["total"] or 0

    sms_today = messages_qs.filter(
        status="sent",
        sent_at__date=today
    ).count()

    scheduled_sms = messages_qs.filter(
        status="scheduled"
    ).count()

    # ===============================
    # RECENTS
    # ===============================
    recent_simple = messages_qs.filter(
        status="sent",
        message_type="simple"
    ).order_by("-sent_at")[:5]

    recent_campaign = messages_qs.filter(
        status="sent",
        message_type="campaign"
    ).order_by("-sent_at")[:5]

    pending_simple = messages_qs.filter(
        status="scheduled",
        message_type="simple"
    ).order_by("scheduled_at")[:5]

    pending_campaigns = messages_qs.filter(
        status="scheduled",
        message_type="campaign"
    ).order_by("scheduled_at")[:5]

    # ===============================
    # HISTORIQUE JOUR (CORRIGÉ)
    # ===============================
    today_history = messages_qs.filter(
        status="sent",
        sent_at__date=today
    ).order_by("-sent_at")[:20]

    # ===============================
    # GRAPH OPTIMISÉ
    # ===============================
    daily_stats = (
        messages_qs.filter(
            status="sent",
            sent_at__date__gte=start_date
        )
        .annotate(date=TruncDate("sent_at"))
        .values("date")
        .annotate(count=Count("id"))
        .order_by("date")
    )

    stats_dict = {
        item["date"]: item["count"]
        for item in daily_stats
    }

    daily_data = []

    for i in range(days_range):
        day = start_date + timedelta(days=i)

        daily_data.append({
            "date": day.strftime("%d/%m"),
            "count": stats_dict.get(day, 0)
        })

    # ===============================
    # FILTRES (FIX TEMPLATE BUG)
    # ===============================
    filters = [
        {"value": "1", "label": "Aujourd’hui"},
        {"value": "7", "label": "7 jours"},
        {"value": "30", "label": "30 jours"},
    ]

    # ===============================
    # CONTEXT
    # ===============================
    context = {

        "balance": balance,

        "total_sms": total_sms,
        "sms_today": sms_today,
        "scheduled_sms": scheduled_sms,
        "total_spent": total_spent,

        "recent_simple": recent_simple,
        "recent_campaign": recent_campaign,

        "pending_simple": pending_simple,
        "pending_campaigns": pending_campaigns,

        "today_history": today_history,

        "daily_data": json.dumps(daily_data),

        "filters": filters,
        "period": period,
    }

    return render(request, "messaging/dashboard.html", context)


# =========================================================
# HISTORY
# =========================================================

@login_required
def message_history_view(request):

    # ===============================
    # BASE QUERY
    # ===============================
    if is_company_admin(request.user):
        qs = Message.objects.filter(company=request.user.company)
    else:
        qs = Message.objects.filter(user=request.user)

    # ===============================
    # FILTRES
    # ===============================
    msg_type = request.GET.get("type")
    status = request.GET.get("status")
    phone = request.GET.get("phone")
    start = request.GET.get("start")
    end = request.GET.get("end")
    search = request.GET.get("q")

    if msg_type:
        qs = qs.filter(message_type=msg_type)

    if status:
        qs = qs.filter(status=status)

    if phone:
        qs = qs.filter(phone__icontains=phone)

    if start:
        qs = qs.filter(created_at__date__gte=start)

    if end:
        qs = qs.filter(created_at__date__lte=end)

    # ===============================
    # RECHERCHE GLOBALE
    # ===============================
    if search:
        qs = qs.filter(
            Q(phone__icontains=search) |
            Q(message__icontains=search) |
            Q(title__icontains=search)
        )

    # ===============================
    # ORDER
    # ===============================
    qs = qs.order_by("-created_at")

    if request.GET.get("export") == "csv":
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="historique_messages.csv"'

        writer = csv.writer(response)
        writer.writerow([
            "date_creation",
            "titre",
            "type",
            "statut",
            "telephone",
            "message",
            "cout",
            "date_programmee",
            "date_envoi",
            "campagne",
        ])

        for msg in qs.select_related("campaign")[:5000]:
            writer.writerow([
                msg.created_at.strftime("%Y-%m-%d %H:%M:%S") if msg.created_at else "",
                msg.title,
                msg.message_type,
                msg.status,
                msg.phone,
                msg.message,
                str(msg.cost),
                msg.scheduled_at.strftime("%Y-%m-%d %H:%M:%S") if msg.scheduled_at else "",
                msg.sent_at.strftime("%Y-%m-%d %H:%M:%S") if msg.sent_at else "",
                msg.campaign.name if msg.campaign else "",
            ])

        return response

    # ===============================
    # PAGINATION
    # ===============================
    paginator = Paginator(qs, 20)  # 20 par page (plus pro que 50)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # ===============================
    # RENDER
    # ===============================
    return render(request, 'messaging/history.html', {
        'messages': page_obj,
        'page_obj': page_obj,
    })



# =========================================================
# SENDERS (ENTREPRISE)
# =========================================================

@login_required
def senders_list(request):

    is_platform_admin = request.user.is_super_admin()

    if is_platform_admin:
        senders = Sender.objects.all()
    elif request.user.is_admin():
        senders = Sender.objects.filter(company=request.user.company)
    else:
        return render(request, "messaging/forbidden.html")

    return render(request, 'messaging/senders_list.html', {
        'senders': senders,
        'is_platform_admin': is_platform_admin
    })


@login_required
def sender_create(request):

    if not request.user.is_admin() or not request.user.company:
        return render(request, "messaging/forbidden.html")

    if request.method == 'POST':

        name = request.POST.get('name')

        if not name:
            messages.error(request, "Nom obligatoire")
            return redirect('sender_create')

        Sender.objects.create(
            company=request.user.company,
            created_by=request.user,
            name=name.upper(),
            status='pending'  # 🔥 IMPORTANT
        )

        messages.success(request, "Expéditeur créé, en attente de validation")

        return redirect('senders_list')

    return render(request, 'messaging/sender_create.html')


@login_required
def sender_edit(request, pk):

    if not request.user.is_admin() or not request.user.company:
        return render(request, "messaging/forbidden.html")

    sender = get_object_or_404(
        Sender,
        id=pk,
        company=request.user.company
    )

    if request.method == 'POST':

        name = request.POST.get('name')

        if not name:
            messages.error(request, "Nom obligatoire")
            return redirect('sender_edit', pk=pk)

        sender.name = name.upper()
        sender.status = 'pending'  # 🔥 reset validation si modifié
        sender.save()

        messages.success(request, "Expéditeur modifié (revalidation requise)")

        return redirect('senders_list')

    return render(request, 'messaging/sender_edit.html', {
        'sender': sender
    })


@login_required
def sender_delete(request, pk):

    if not request.user.is_admin() or not request.user.company:
        return render(request, "messaging/forbidden.html")

    sender = get_object_or_404(
        Sender,
        id=pk,
        company=request.user.company
    )

    # ===============================
    # 🔒 SÉCURITÉ 1 : sender approuvé
    # ===============================
    if sender.status == "approved":
        messages.error(
            request,
            "Impossible de supprimer un expéditeur approuvé."
        )
        return redirect('senders_list')

    # ===============================
    # 🔒 SÉCURITÉ 2 : sender utilisé
    # ===============================
    from messaging.models import SMS, Campaign

    is_used = (
        SMS.objects.filter(sender=sender).exists()
        or
        Campaign.objects.filter(sender=sender).exists()
    )

    if is_used:
        messages.error(
            request,
            "Impossible de supprimer cet expéditeur car il est déjà utilisé dans des SMS ou campagnes."
        )
        return redirect('senders_list')

    # ===============================
    # ✅ CONFIRMATION
    # ===============================
    if request.method == "POST":
        sender.delete()
        messages.success(request, "Expéditeur supprimé avec succès")
        return redirect('senders_list')

    return render(request, "messaging/sender_delete.html", {
        "sender": sender
    })


# =========================================================
# ADMIN PLATEFORME - VALIDATION
# =========================================================

@login_required
def admin_senders(request):

    if not request.user.is_super_admin():
        return redirect('dashboard')

    senders = Sender.objects.all().order_by('-created_at')

    return render(request, 'messaging/admin_senders.html', {
        'senders': senders,
        'is_platform_admin': True
    })


@login_required
def approve_sender(request, sender_id):

    if not request.user.is_super_admin():
        return redirect('dashboard')

    sender = get_object_or_404(Sender, id=sender_id)

    sender.status = 'approved'
    sender.approved_by = request.user
    sender.approved_at = timezone.now()
    sender.save()

    messages.success(request, f"{sender.name} approuvé avec succès")

    return redirect('admin_senders')


@login_required
def reject_sender(request, sender_id):

    if not request.user.is_super_admin():
        return redirect('dashboard')

    sender = get_object_or_404(Sender, id=sender_id)

    sender.status = 'rejected'
    sender.save()

    messages.warning(request, f"{sender.name} rejeté")

    return redirect('admin_senders')


# =========================================================
# DOWNLOAD EXCEL
# =========================================================

def download_model_excel(request):

    file_path = os.path.join("media", "modele_import_sms.xlsx")

    if not os.path.exists(file_path):
        return HttpResponse("Fichier introuvable", status=404)

    return FileResponse(open(file_path, 'rb'), as_attachment=True)





# =========================================================
# MESSAGE SEARCH API
# =========================================================
@login_required
def message_search_api(request):
    """
    API de recherche live pour les messages (AJAX)
    """

    user = request.user
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status")
    message_type = request.GET.get("type")

    # =========================
    # BASE QUERY (SÉCURITÉ MULTI-TENANT)
    # =========================
    qs = Message.objects.select_related("campaign", "company")

    # 🔒 SUPER ADMIN → voit tout
    if user.role == "super_admin":
        pass

    # 🔒 ADMIN → messages de son entreprise
    elif user.role == "admin":
        qs = qs.filter(company=user.company)

    # 🔒 USER → uniquement ses messages
    else:
        qs = qs.filter(user=user)

    # =========================
    # FILTRES
    # =========================
    if query:
        qs = qs.filter(
            Q(phone__icontains=query) |
            Q(message__icontains=query) |
            Q(title__icontains=query)
        )

    if status:
        qs = qs.filter(status=status)

    if message_type:
        qs = qs.filter(message_type=message_type)

    # =========================
    # LIMITATION (PERFORMANCE)
    # =========================
    qs = qs.order_by("-created_at")[:50]

    # =========================
    # FORMAT JSON
    # =========================
    data = []

    for m in qs:
        data.append({
            "id": m.id,
            "title": m.title,
            "phone": m.phone,
            "message": m.message[:80],
            "status": m.status,
            "type": m.message_type,
            "cost": float(m.cost),
            "date": m.created_at.strftime("%d/%m %H:%M"),
            "campaign": m.campaign.name if m.campaign else None,
        })

    return JsonResponse({
        "success": True,
        "count": len(data),
        "results": data
    })



# =========================================================
# RECHARGE ENTREPRISE
# =========================================================

@login_required
def company_recharge_view(request, company_id):

    if not request.user.is_super_admin():
        return render(request, "messaging/forbidden.html")

    company = get_object_or_404(Company, id=company_id)

    form = RechargeForm(request.POST or None)

    if request.method == "POST" and form.is_valid():

        amount = Decimal(form.cleaned_data["amount"])

        company.balance += amount
        company.save()

        messages.success(request, "Recharge effectuée")

        return redirect("company_list")

    return render(request, "accounts/company_recharge.html", {
        "form": form,
        "company": company
    })
