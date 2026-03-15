import random
import string
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import make_password
from django.db import transaction
from django.db.models import Sum, Count, Q
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from messaging.models import Message

from .models import Company, User, CompanyTransaction, UserCreditTransaction
from .forms import (
    CompanyUserCreateForm,
    CompanyUserUpdateForm,
    CompanyForm,
    RechargeForm,
    UserRechargeForm,
    UserProfileForm
)
from .utils import get_managed_company_or_forbidden

import json

from django.contrib.auth import authenticate, login




# =================================================
# PAGE DE CONNEXION
# =================================================
def login_view(request):

    if request.method == "POST":

        username = request.POST.get("username")
        password = request.POST.get("password")
        remember_me = request.POST.get("remember_me")

        user = authenticate(request, username=username, password=password)

        if user is not None:
            messages.error(request, "Nom d'utilisateur ou mot de passe incorrect.")

            login(request, user)

            # Gestion "Se souvenir de moi"
            if not remember_me:
                request.session.set_expiry(0)

            return redirect("redirect_after_login")

    return render(request, "accounts/login.html")


# ---------------------------------------------------
# DASHBOARD ADMIN PLATEFORME
# ---------------------------------------------------

@login_required
def accounts_dashboard_view(request):

    # sécurité : seulement admin plateforme
    if request.user.role != "admin" or request.user.company is not None:
        return redirect("dashboard")

    today = timezone.now().date()

    # =================================================
    # KPI GLOBAL
    # =================================================

    total_companies = Company.objects.count()

    active_companies = Company.objects.filter(
        is_active=True
    ).count()

    total_sms = Message.objects.filter(
        status="sent"
    ).count()

    total_revenue = Message.objects.filter(
        status="sent"
    ).aggregate(
        total=Sum("cost")
    )["total"] or 0

    sms_today = Message.objects.filter(
        status="sent",
        sent_at__date=today
    ).count()

    active_users = User.objects.filter(
        is_active=True
    ).count()

    total_balance = Company.objects.aggregate(
        total=Sum("balance")
    )["total"] or 0


    # =================================================
    # TOP ENTREPRISES
    # =================================================

    top_companies = Company.objects.annotate(
        sms_count=Count("message", filter=Q(message__status="sent"))
    ).order_by("-sms_count")[:5]


    # =================================================
    # TOP UTILISATEURS
    # =================================================

    top_users = User.objects.annotate(
        sms_count=Count("message", filter=Q(message__status="sent"))
    ).order_by("-sms_count")[:5]


    # =================================================
    # HISTORIQUE RECHARGEMENT
    # =================================================

    recent_recharges = CompanyTransaction.objects.filter(
        transaction_type="credit"
    ).select_related("company").order_by("-created_at")[:10]


    # =================================================
    # TAUX CONSOMMATION ENTREPRISE
    # =================================================

    companies_consumption = []

    companies = Company.objects.annotate(
        total_spent=Sum("message__cost"),
        total_sms=Count("message", filter=Q(message__status="sent"))
    ).filter(total_sms__gt=0)

    for comp in companies:

        spent = comp.total_spent or 0
        balance = comp.balance or 0

        if (balance + spent) > 0:
            rate = (spent / (balance + spent)) * 100
        else:
            rate = 0

        companies_consumption.append({
            "name": comp.name,
            "spent": float(spent),
            "balance": float(balance),
            "rate": round(rate, 2)
        })

    companies_consumption = sorted(
        companies_consumption,
        key=lambda x: x["spent"],
        reverse=True
    )[:10]


    # =================================================
    # SMS 7 DERNIERS JOURS
    # =================================================

    daily_data = []

    start_date = today - timedelta(days=6)

    for i in range(7):

        day = start_date + timedelta(days=i)

        count = Message.objects.filter(
            status="sent",
            sent_at__date=day
        ).count()

        daily_data.append({
            "date": day.strftime("%d/%m"),
            "count": count
        })


    # =================================================
    # CONTEXT
    # =================================================

    context = {

        "total_companies": total_companies,
        "active_companies": active_companies,

        "total_sms": total_sms,
        "total_revenue": total_revenue,

        "sms_today": sms_today,
        "active_users": active_users,

        "total_balance": total_balance,

        "top_companies": top_companies,
        "top_users": top_users,

        "recent_recharges": recent_recharges,

        "companies_consumption": companies_consumption,

        "daily_data": json.dumps(daily_data),

    }

    return render(
        request,
        "accounts/dashboard.html",
        context
    )


# ---------------------------------------------------
# UTILISATEURS ENTREPRISE
# ---------------------------------------------------

# LISTE DES UTILISATEURS D'UNE ENTREPRISE
@login_required
def company_users_list_view(request, company_id):

    company = get_managed_company_or_forbidden(request, company_id)

    if company is None:
        return render(request, "messaging/forbidden.html")

    # ADMIN PLATEFORME
    if request.user.company is None:
        users = User.objects.filter(company=company)

    # ADMIN ENTREPRISE
    else:
        users = User.objects.filter(
            company=company,
            role="user"
        )

    return render(request, "accounts/company_users_list.html", {
        "company": company,
        "users": users,
    })


# CRÉATION D'UTILISATEUR POUR UNE ENTREPRISE
@login_required
def company_user_create_view(request, company_id):

    company = get_managed_company_or_forbidden(request, company_id)

    if company is None:
        return render(request, "messaging/forbidden.html")

    is_company_admin = request.user.company is not None

    if request.method == "POST":

        form = CompanyUserCreateForm(request.POST)

        # 🔴 IMPORTANT : assigner company avant validation
        form.instance.company = company

        if is_company_admin:
            form.fields["role"].choices = [("user", "User")]

        if form.is_valid():

            user_obj = form.save(commit=False)

            if is_company_admin:
                user_obj.role = "user"

            user_obj.save()

            return render(
                request,
                "accounts/user_created.html",
                {
                    "created_user": user_obj,
                    "company": company,
                }
            )

        else:
            print("Form errors:", form.errors)

            messages.error(
                request,
                "Erreur lors de la création de l'utilisateur."
            )

    else:

        form = CompanyUserCreateForm(
            initial={
                "is_active": True,
                "role": "user"
            }
        )

        form.instance.company = company

        if is_company_admin:
            form.fields["role"].choices = [("user", "User")]

    return render(
        request,
        "accounts/company_user_form.html",
        {
            "form": form,
            "company": company,
            "is_edit": False,
        }
    )


# MODIFICATION D'UTILISATEUR POUR UNE ENTREPRISE
@login_required
def company_user_update_view(request, company_id, user_id):

    company = get_managed_company_or_forbidden(request, company_id)

    if company is None:
        return render(request, "messaging/forbidden.html")

    user_obj = get_object_or_404(User, pk=user_id, company=company)

    is_company_admin = request.user.company is not None

    if request.method == "POST":

        form = CompanyUserUpdateForm(request.POST, instance=user_obj)

        if is_company_admin:
            form.fields['role'].choices = [('user', 'User')]

        if form.is_valid():

            updated_user = form.save(commit=False)

            if is_company_admin:
                updated_user.role = 'user'

            updated_user.save()

            messages.success(request, "Utilisateur mis à jour.")

            return redirect(
                'company_users_list',
                company_id=company.id
            )

    else:

        form = CompanyUserUpdateForm(instance=user_obj)

        if is_company_admin:
            form.fields['role'].choices = [('user', 'User')]

    return render(request, "accounts/company_user_form.html", {
        "form": form,
        "company": company,
        "user_obj": user_obj,
        "is_edit": True,
    })


# ACTIVATION/DÉSACTIVATION D'UTILISATEUR POUR UNE ENTREPRISE
@login_required
def company_user_toggle_active_view(request, company_id, user_id):

    company = get_managed_company_or_forbidden(request, company_id)

    if company is None:
        return render(request, "messaging/forbidden.html")

    if request.method != "POST":
        return redirect('company_users_list', company_id=company.id)

    user_obj = get_object_or_404(User, pk=user_id, company=company)

    if user_obj.pk == request.user.pk:
        messages.error(request, "Action non autorisée.")
        return redirect('company_users_list', company_id=company.id)

    user_obj.is_active = not user_obj.is_active
    user_obj.save(update_fields=['is_active'])

    return redirect('company_users_list', company_id=company.id)


# SUPPRESSION D'UTILISATEUR POUR UNE ENTREPRISE
@login_required
def company_user_delete_view(request, company_id, user_id):

    company = get_managed_company_or_forbidden(request, company_id)

    if company is None:
        return render(request, "messaging/forbidden.html")

    if request.method != "POST":
        return redirect('company_users_list', company_id=company.id)

    user_obj = get_object_or_404(User, pk=user_id, company=company)

    # empêcher suppression de soi-même
    if user_obj.pk == request.user.pk:
        messages.error(request, "Vous ne pouvez pas supprimer votre propre compte.")
        return redirect('company_users_list', company_id=company.id)

    # empêcher suppression de l'admin entreprise
    if user_obj.role == "admin":
        messages.error(request, "Impossible de supprimer l'administrateur de l'entreprise.")
        return redirect('company_users_list', company_id=company.id)

    user_obj.delete()

    messages.success(request, "Utilisateur supprimé avec succès.")

    return redirect('company_users_list', company_id=company.id)





# ---------------------------------------------------
# ENTREPRISES
# ---------------------------------------------------

# LISTE DES ENTREPRISES
@login_required
def company_list_view(request):

    if request.user.role != "admin":
        return redirect("dashboard")

    companies = Company.objects.all()

    return render(request, "accounts/company_list.html", {
        "companies": companies
    })


# GÉNÉRATION DE MOT DE PASSE ALÉATOIRE
def generate_password(length=10):

    characters = string.ascii_letters + string.digits

    return ''.join(
        random.choice(characters) for _ in range(length)
    )


# CRÉATION D'ENTREPRISE
@login_required
def company_create_view(request):

    if request.user.role != "admin":
        return redirect("dashboard")

    if request.method == "POST":

        form = CompanyForm(request.POST)

        if form.is_valid():

            company = form.save()

            username = company.name.lower().replace(" ", "") + "_admin"

            raw_password = generate_password()

            user = User.objects.create(
                username=username,
                company=company,
                role="admin",
                password=make_password(raw_password),
                email=f"{username}@example.com"
            )

            return render(request, "accounts/company_created.html", {
                "company": company,
                "username": username,
                "password": raw_password
            })

    else:
        form = CompanyForm()

    return render(request, "accounts/company_form.html", {
        "form": form
    })


# MODIFICATION D'ENTREPRISE
@login_required
def company_update_view(request, pk):

    if request.user.role != "admin":
        return redirect("dashboard")

    company = get_object_or_404(Company, pk=pk)

    if request.method == "POST":

        form = CompanyForm(request.POST, instance=company)

        if form.is_valid():
            form.save()
            return redirect("company_list")

    else:

        form = CompanyForm(instance=company)

    return render(request, "accounts/company_form.html", {
        "form": form
    })


# SUPPRESSION D'ENTREPRISE
@login_required
def company_delete_view(request, pk):

    if request.user.role != "admin":
        return redirect("dashboard")

    company = get_object_or_404(Company, pk=pk)

    if request.method == "POST":

        company.delete()

        return redirect("company_list")

    return render(request, "accounts/company_confirm_delete.html", {
        "company": company
    })


# ---------------------------------------------------
# RECHARGES ENTREPRISE
# ---------------------------------------------------

# RECHARGEMENT D'ENTREPRISE
@login_required
def company_recharge_view(request, pk):

    if request.user.role != "admin":
        return redirect("dashboard")

    company = Company.objects.get(pk=pk)

    if request.method == "POST":

        form = RechargeForm(request.POST)

        if form.is_valid():

            amount = form.cleaned_data["amount"]

            company.balance += amount
            company.save()

            CompanyTransaction.objects.create(
                company=company,
                amount=amount,
                transaction_type='credit',
                description="Recharge admin"
            )

            return redirect("company_list")

    else:

        form = RechargeForm()

    return render(request, "accounts/company_recharge.html", {
        "form": form,
        "company": company
    })


# ---------------------------------------------------
# RECHARGE UTILISATEUR
# ---------------------------------------------------

# RECHARGEMENT D'UTILISATEUR
@login_required
def company_user_recharge_view(request, company_id, user_id):

    company = get_managed_company_or_forbidden(request, company_id)

    if company is None:
        return render(request, "messaging/forbidden.html")

    if request.user.role != "admin":
        return render(request, "messaging/forbidden.html")

    target_user = get_object_or_404(User, pk=user_id, company=company)

    if target_user.role != "user":
        return render(request, "messaging/forbidden.html")

    if request.method == "POST":

        form = UserRechargeForm(request.POST)

        if form.is_valid():

            amount = form.cleaned_data["amount"]

            if amount <= 0:
                messages.error(request, "Montant invalide.")
                return redirect(
                    'company_user_recharge',
                    company_id=company.id,
                    user_id=target_user.id
                )

            if company.balance < amount:
                messages.error(request, "Solde entreprise insuffisant.")
                return redirect(
                    'company_user_recharge',
                    company_id=company.id,
                    user_id=target_user.id
                )

            with transaction.atomic():

                company.balance -= amount
                company.save(update_fields=['balance'])

                target_user.credit_balance += amount
                target_user.save(update_fields=['credit_balance'])

                CompanyTransaction.objects.create(
                    company=company,
                    amount=amount,
                    transaction_type='debit',
                    description=f"Allocation crédit vers {target_user.username}"
                )

                UserCreditTransaction.objects.create(
                    company=company,
                    user=target_user,
                    amount=amount,
                    transaction_type='credit',
                    description=f"Recharge par {request.user.username}"
                )

            messages.success(request, "Crédit utilisateur alimenté.")

            return redirect(
                'company_users_list',
                company_id=company.id
            )

    else:
        form = UserRechargeForm()

    return render(request, "accounts/user_recharge.html", {
        "form": form,
        "company": company,
        "target_user": target_user,
    })




# =====================================================
# PROFIL UTILISATEUR
# =====================================================
@login_required
def user_profile_view(request):

    user = request.user

    if request.method == "POST":

        form = UserProfileForm(request.POST, instance=user)

        if form.is_valid():

            user = form.save()

            messages.success(
                request,
                "Profil mis à jour avec succès."
            )

            return redirect("user_profile")

    else:

        form = UserProfileForm(instance=user)

    return render(
        request,
        "accounts/profile.html",
        {
            "form": form
        }
    )


# =====================================================
# ACTIVER/DÉSACTIVER ENTREPRISE
# =====================================================
@login_required
def company_toggle_active_view(request, pk):

    if request.user.role != "admin":
        return redirect("dashboard")

    company = get_object_or_404(Company, pk=pk)

    company.is_active = not company.is_active
    company.save()

    return redirect("company_list")