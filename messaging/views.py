import re
import math
import pandas as pd
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import FileResponse
from django.utils.dateparse import parse_datetime
from django.db.models import Sum, Count
from django.utils import timezone
from datetime import timedelta

from messaging.services import send_sms
from messaging.models import Message
from .models import Campaign
from accounts.models import Company


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
        "daily_data": daily_data
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

    return render(request, "messaging/send_sms.html")


#############################################################
# CAMPAGNE EXCEL + PLANIFICATION
#############################################################

@login_required
def campaign_upload_view(request):

    if request.method == "POST":

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

            name = str(row.get("name", ""))

            if "custom_message" in df.columns and not pd.isna(row.get("custom_message")):
                final_message = row.get("custom_message")
            else:
                final_message = message_text.replace("{{name}}", name)

            sms_parts = math.ceil(len(final_message) / 160)
            total_sms_needed += sms_parts

            valid_rows.append((phone, final_message))

        total_cost = total_sms_needed * SMS_PRICE

        if not scheduled_at and company.balance < total_cost:
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

    return render(request, "messaging/campaign_upload.html")


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

    # ✅ UTILISATION DU MANAGER SÉCURISÉ
    messages = Message.objects.for_company(company).filter(
        status='sent',
        sent_at__date__gte=start_date
    )

    total_sms = messages.count()
    total_spent = messages.aggregate(Sum('cost'))['cost__sum'] or 0

    sms_today = Message.objects.for_company(company).filter(
        status='sent',
        sent_at__date=today
    ).count()

    daily_data = []

    for i in range(days_range):
        day = start_date + timedelta(days=i)

        count = Message.objects.for_company(company).filter(
            status='sent',
            sent_at__date=day
        ).count()

        daily_data.append({
            "date": day.strftime("%d/%m"),
            "count": count
        })

    context = {
        "total_sms": total_sms,
        "total_spent": total_spent,
        "sms_today": sms_today,
        "balance": company.balance,
        "daily_data": daily_data,
        "period": period
    }

    return render(request, "messaging/dashboard.html", context)