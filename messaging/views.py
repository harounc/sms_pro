import re
import math
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import FileResponse
from django.http import HttpResponse
from django.utils.dateparse import parse_datetime
from django.db.models import Sum, Count
from django.utils import timezone
from datetime import datetime, timedelta
import csv

from messaging.services import send_sms
from messaging.models import Message
from .models import Campaign, Sender
from accounts.models import Company

from django.core.paginator import Paginator

from contacts.models import ContactGroup





SMS_PRICE = 19

#############################################################
# Dashboard Admin (Global)
#############################################################

@login_required
def admin_dashboard_view(request):

    if request.user.role != "admin":
        return render(request, "messaging/forbidden.html")

    today = timezone.now().date()

    total_sms = Message.objects.filter(status='sent').count()

    total_revenue = Message.objects.filter(
        status='sent'
    ).aggregate(Sum('cost'))['cost__sum'] or 0

    total_companies = Company.objects.count()

    top_companies = Company.objects.annotate(
        sms_count=Count('message')
    ).order_by('-sms_count')[:5]

    daily_data = []
    start_date = today - timedelta(days=6)

    for i in range(7):
        day = start_date + timedelta(days=i)

        count = Message.objects.filter(
            status='sent',
            sent_at__date=day
        ).count()

        daily_data.append({
            "date": day.strftime("%d/%m"),
            "count": count
        })

    context = {
        "total_sms": total_sms,
        "total_revenue": total_revenue,
        "total_companies": total_companies,
        "top_companies": top_companies,
        "daily_data": json.dumps(daily_data)
    }

    return render(request, "messaging/admin_dashboard.html", context)


#############################################################
# Téléchargement modèle Excel
#############################################################

def download_model_excel(request):
    file_path = "/mnt/data/modele_import_sms.xlsx"
    return FileResponse(
        open(file_path, 'rb'),
        as_attachment=True,
        filename="modele_import_sms.xlsx"
    )


#############################################################
# SMS SIMPLE (multi numéros + planification)
#############################################################

@login_required
def send_sms_view(request):

    contact_groups = ContactGroup.objects.filter(owner=request.user)

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
        name = request.POST.get("name", "")
        scheduled_input = request.POST.get("scheduled_at")

        if not numbers_input:
            return render(request, "messaging/send_sms.html", {
                "error": "Veuillez saisir au moins un numéro."
            })

        scheduled_at = parse_datetime(scheduled_input) if scheduled_input else None

        numbers = [num.strip() for num in numbers_input.split(";")]

        total_sent = 0
        invalid_numbers = []

        for phone in numbers:

            if not re.fullmatch(r"\+225\d{10}", phone):
                invalid_numbers.append(phone)
                continue

            final_message = message.replace("{{name}}", name)

            result = send_sms(
                request.user,
                phone,
                final_message,
                scheduled_at=scheduled_at
            )

            if result["success"]:
                total_sent += 1

        if invalid_numbers:
            return render(request, "messaging/send_sms.html", {
                "error": f"Numéros invalides : {', '.join(invalid_numbers)}"
            })

        if scheduled_at:
            return render(request, "messaging/send_sms.html", {
                "success": f"{total_sent} SMS planifiés."
            })

        return render(request, "messaging/send_sms.html", {
            "success": f"{total_sent} SMS envoyés."
        })

    return render(request, "messaging/send_sms.html", {
        "contact_groups": contact_groups,
        "senders": senders
    })


#############################################################
# CAMPAGNE EXCEL + PLANIFICATION
#############################################################

@login_required
def campaign_upload_view(request):

    contact_groups = ContactGroup.objects.filter(owner=request.user)

    senders = Sender.objects.filter(
        company=request.user.company,
        status='approved'
    )
    

    if not senders.exists():
        return render(request, "messaging/campaign_upload.html", {
            "error": "Aucun expéditeur approuvé disponible. Veuillez contacter l'administrateur."
        })


    try:
        import pandas as pd
    except ModuleNotFoundError:
        pd = None

    if request.method == "POST":

        if pd is None:
            return render(request, "messaging/campaign_upload.html", {
                "error": "Fonction indisponible: pandas n'est pas installé sur le serveur."
            })

        file = request.FILES.get("file")
        message_text = request.POST.get("message")
        scheduled_input = request.POST.get("scheduled_at")

        if not file:
            return render(request, "messaging/campaign_upload.html", {
                "error": "Veuillez importer un fichier Excel."
            })

        scheduled_at = parse_datetime(scheduled_input) if scheduled_input else None

        df = pd.read_excel(file, dtype=str)

        if "phone" not in df.columns:
            return render(request, "messaging/campaign_upload.html", {
                "error": "La colonne 'phone' est obligatoire."
            })

        company = request.user.company

        valid_rows = []
        total_sms_needed = 0

        for _, row in df.iterrows():

            phone = str(row["phone"]).strip()

            if not re.fullmatch(r"\+225\d{10}", phone):
                continue

            raw_name = row.get("name", "")
            if pd.isna(raw_name):
                raw_name = ""
            name = str(raw_name).strip()

            raw_custom = row.get("custom_message", "") if "custom_message" in df.columns else ""
            if pd.isna(raw_custom):
                raw_custom = ""
            custom_message = str(raw_custom).strip()

            if custom_message:
                final_message = custom_message
            else:
                final_message = (message_text or "")

            if "{{name}}" in final_message:
                final_message = final_message.replace("{{name}}", name)

            if not str(final_message).strip():
                continue

            sms_parts = math.ceil(len(final_message) / 350)
            total_sms_needed += sms_parts

            valid_rows.append((phone, final_message))

        total_cost = total_sms_needed * SMS_PRICE

        if not scheduled_at:
            if request.user.role == 'user':
                if request.user.credit_balance < total_cost:
                    return render(request, "messaging/campaign_upload.html", {
                        "error": f"Crédit utilisateur insuffisant. Coût total estimé : {total_cost:.2f} crédits."
                    })
            else:
                if company.balance < total_cost:
                    return render(request, "messaging/campaign_upload.html", {
                        "error": f"Solde insuffisant. Coût total estimé : {total_cost:.2f} crédits."
                    })

        # ✅ AJOUT DE COMPANY
        campaign = Campaign.objects.create(
            user=request.user,
            company=company,
            name="Campagne Excel",
            message=message_text
        )

        total_sent = 0

        for phone, final_message in valid_rows:

            result = send_sms(
                user=request.user,
                phone=phone,
                text=final_message,
                message_type='campaign',
                campaign=campaign,
                scheduled_at=scheduled_at
            )

            if result["success"]:
                total_sent += 1

        if scheduled_at:
            return render(request, "messaging/campaign_upload.html", {
                "success": f"Campagne planifiée. {total_sent} SMS programmés."
            })

        return render(request, "messaging/campaign_upload.html", {
            "success": f"Campagne terminée. {total_sent} SMS envoyés."
        })

    return render(request, "messaging/campaign_upload.html", {
        "contact_groups": contact_groups,
        "senders": senders
    })


#############################################################
# Dashboard Utilisateur (Sécurisé Multi-Entreprise)
#############################################################

@login_required
def dashboard_view(request):

    user = request.user
    company = user.company

    period = request.GET.get("period", "7")

    today = timezone.now().date()

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

        messages_qs = Message.objects.filter(
            company=company
        )

        balance = company.balance

    else:

        messages_qs = Message.objects.filter(
            company=company,
            user=user
        )

        balance = user.credit_balance

    # ===============================
    # STATISTIQUES
    # ===============================

    sent_messages = messages_qs.filter(
        status="sent",
        sent_at__date__gte=start_date
    )

    total_sms = sent_messages.count()

    total_spent = sent_messages.aggregate(
        Sum("cost")
    )["cost__sum"] or 0

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
    # GRAPH
    # ===============================

    daily_data = []

    for i in range(days_range):

        day = start_date + timedelta(days=i)

        count = messages_qs.filter(
            status="sent",
            sent_at__date=day
        ).count()

        daily_data.append({
            "date": day.strftime("%d/%m"),
            "count": count
        })

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

        "daily_data": json.dumps(daily_data),

        "period": period,
    }

    return render(
        request,
        "messaging/dashboard.html",
        context
    )

#############################################################
# Historique (liste + filtres + export CSV)
#############################################################

@login_required
def message_history_view(request):

    user = request.user
    company = user.company

    qs = Message.objects.for_company(company)

    msg_type = request.GET.get('type', '')
    status = request.GET.get('status', '')
    phone = request.GET.get('phone', '').strip()
    start = request.GET.get('start', '')
    end = request.GET.get('end', '')

    if msg_type in {'simple', 'campaign'}:
        qs = qs.filter(message_type=msg_type)

    if status in {'scheduled', 'pending', 'sent', 'failed'}:
        qs = qs.filter(status=status)

    if phone:
        qs = qs.filter(phone__icontains=phone)

    if start:
        try:
            start_dt = datetime.strptime(start, "%Y-%m-%d")
            start_dt = timezone.make_aware(start_dt)
            qs = qs.filter(created_at__gte=start_dt)
        except ValueError:
            pass

    if end:
        try:
            end_dt = datetime.strptime(end, "%Y-%m-%d")
            end_dt = timezone.make_aware(end_dt)
            end_dt = end_dt + timedelta(days=1) - timedelta(seconds=1)
            qs = qs.filter(created_at__lte=end_dt)
        except ValueError:
            pass

    qs = qs.select_related(
        'campaign',
        'user'
    ).order_by('-created_at')

    # Export CSV
    export = request.GET.get('export', '')

    if export == 'csv':

        response = HttpResponse(
            content_type='text/csv; charset=utf-8'
        )

        response['Content-Disposition'] = \
            'attachment; filename="historique_messages.csv"'

        writer = csv.writer(response)

        writer.writerow([
            'date_creation',
            'type',
            'statut',
            'telephone',
            'message',
            'cout',
            'segments',
            'date_programmee',
            'date_envoi',
            'campagne'
        ])

        for m in qs[:5000]:

            segments = math.ceil(len(m.message) / 160)

            writer.writerow([
                m.created_at.strftime("%Y-%m-%d %H:%M:%S") if m.created_at else '',
                m.message_type,
                m.status,
                m.phone,
                m.message,
                str(m.cost),
                segments,
                m.scheduled_at.strftime("%Y-%m-%d %H:%M:%S") if m.scheduled_at else '',
                m.sent_at.strftime("%Y-%m-%d %H:%M:%S") if m.sent_at else '',
                m.campaign.name if m.campaign else ''
            ])

        return response

    paginator = Paginator(qs, 50)

    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'messages': page_obj,
        'page_obj': page_obj,
        'type': msg_type,
        'status': status,
        'phone': phone,
        'start': start,
        'end': end,
    }

    return render(
        request,
        'messaging/history.html',
        context
    )


# ==============================
# CRUD EXPEDITEUR _ Sender
# ==============================


# List senders
@login_required
def senders_list(request):
    
    # Admin plateforme
    if request.user.role == 'admin' and not request.user.company:
        senders = Sender.objects.all().order_by('-created_at')

        context = {
            'senders': senders,
            'is_platform_admin': True
        }
    
    # Admin entreprise
    else:
        senders = Sender.objects.filter(
        company=request.user.company
    ).order_by('-created_at')

        context = {
            'senders': senders,
            'is_platform_admin': False
        }
    
    return render(request, 'messaging/senders_list.html', context)


# Create sender
@login_required
def sender_create(request):
    
    if request.method == 'POST':

        name = request.POST.get('name')

        Sender.objects.create(
            company=request.user.company,
            created_by=request.user,
            name=name.upper()
        )
        
        return redirect('senders_list')

    return render(request, 'messaging/sender_create.html')


# Edit sender
@login_required
def sender_edit(request, pk):
    
    sender = get_object_or_404(Sender, id=pk)
    
    if request.method == 'POST':
        
        name = request.POST.get('name')
        
        sender.name = name.upper()
        sender.save()
        
        return redirect('senders_list')
    
    return render(request, 'messaging/sender_edit.html', {
        'sender': sender
    })


# Delete sender
@login_required
def sender_delete(request, pk):
    
    sender = get_object_or_404(Sender, pk=pk)

    sender.delete()
        
    return redirect('senders_list')

# ============================
# Admin Sender Management
# ============================

# Admin senders
@login_required
def admin_senders(request):
    
    if request.user.role != 'admin' or request.user.company:
        return redirect('dashboard')
    
    senders = Sender.objects.all().order_by('-created_at')
    
    return render(request, 'messaging/admin_senders.html', {
        'senders': senders
    })


# Approve sender
@login_required
def approve_sender(request, sender_id):

    if request.user.role != 'admin' or request.user.company:
        return redirect('dashboard')
    
    sender = get_object_or_404(Sender, id=sender_id)
    
    sender.status = 'approved'
    sender.approved_by = request.user
    sender.approved_at = timezone.now()
    sender.save()
    
    return redirect('admin_senders')


# Reject sender
@login_required
def reject_sender(request, sender_id):

    if request.user.role != 'admin' or request.user.company:
        return redirect('dashboard')
    
    sender = get_object_or_404(Sender, id=sender_id)
    
    sender.status = 'rejected'
    sender.rejected_by = request.user
    sender.rejected_at = timezone.now()
    sender.save()
    
    return redirect('admin_senders')
