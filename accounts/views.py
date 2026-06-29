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
    CompanyForm,
    RechargeForm,
    UserRechargeForm,
    UserProfileForm,
    UserForm,
)
from .utils import get_managed_company_or_403, generate_password

from django.contrib.auth import authenticate, login, update_session_auth_hash



# ===============================
# LOGIN
# ===============================
def login_view(request):

    if request.method == "POST":

        username = request.POST.get("username")
        password = request.POST.get("password")
        remember_me = request.POST.get("remember_me")

        user = authenticate(request, username=username, password=password)

        if user is None:
            messages.error(request, "Nom d'utilisateur ou mot de passe incorrect.")
            return redirect("login")

        if user.company and not user.company.is_active:
            messages.error(request, "Votre entreprise est désactivée.")
            return redirect("login")

        login(request, user)

        if not remember_me:
            request.session.set_expiry(0)

        return redirect("redirect_after_login")

    return render(request, "accounts/login.html")


# ===============================
# DASHBOARD SUPER ADMIN
# ===============================
@login_required
def accounts_dashboard_view(request):

    if not request.user.is_super_admin():
        return redirect("dashboard")

    today = timezone.now().date()

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

    top_companies = Company.objects.annotate(
        sms_count=Count("message", filter=Q(message__status="sent"))
    ).order_by("-sms_count")[:5]

    top_users = User.objects.annotate(
        sms_count=Count("message", filter=Q(message__status="sent"))
    ).order_by("-sms_count")[:5]

    recent_recharges = CompanyTransaction.objects.filter(
        transaction_type="credit"
    ).select_related("company").order_by("-created_at")[:10]

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
    }

    return render(request, "accounts/dashboard.html", context)


# ===============================
# ENTREPRISES
# ===============================

# list companies
@login_required
def company_list_view(request):

    if not request.user.is_super_admin():
        return redirect("dashboard")

    companies = Company.objects.all()

    return render(request, "accounts/company_list.html", {
        "companies": companies
    })



# create company
@login_required
def company_create_view(request):

    if not request.user.is_super_admin():
        return redirect("dashboard")

    if request.method == "POST":

        form = CompanyForm(request.POST)

        if form.is_valid():

            company = form.save()

            username = company.name.lower().replace(" ", "") + "_admin"
            raw_password = generate_password()

            User.objects.create(
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

    return render(request, "accounts/company_form.html", {"form": form})


# update company
@login_required
def company_update_view(request, pk):

    # 🔒 uniquement super admin
    if not request.user.is_super_admin():
        return redirect("dashboard")

    company = get_object_or_404(Company, pk=pk)

    if request.method == "POST":

        company.name = request.POST.get("name")
        company.is_active = request.POST.get("is_active") == "on"

        company.save()

        messages.success(request, "Entreprise mise à jour avec succès.")

        return redirect("company_list")

    return render(request, "accounts/company_form.html", {
        "company": company,
        "is_edit": True
    })

# delete company
@login_required
def company_delete_view(request, pk):

    # 🔒 uniquement super admin
    if not request.user.is_super_admin():
        return redirect("dashboard")

    company = get_object_or_404(Company, pk=pk)

    # 🔒 sécurité : éviter suppression entreprise liée au user actuel
    if request.user.company == company:
        messages.error(request, "Vous ne pouvez pas supprimer votre propre entreprise.")
        return redirect("company_list")

    company.delete()

    messages.success(request, "Entreprise supprimée avec succès.")

    return redirect("company_list")



@login_required
def company_recharge_view(request, pk):

    if not request.user.is_super_admin():
        return render(request, "messaging/forbidden.html")

    company = get_object_or_404(Company, id=pk)

    form = RechargeForm(request.POST or None)

    if request.method == "POST":

        if form.is_valid():

            amount = form.cleaned_data["amount"]

            with transaction.atomic():
                company = Company.objects.select_for_update().get(pk=company.pk)
                company.balance += amount
                company.save(update_fields=["balance"])

                CompanyTransaction.objects.create(
                    company=company,
                    amount=amount,
                    transaction_type="credit",
                    description="Recharge entreprise"
                )

            messages.success(request, f"Recharge de {amount} crédits effectuée")

            return redirect("company_list")

    return render(request, "accounts/company_recharge.html", {
        "form": form,
        "company": company
    })

# ===============================
# USERS ENTREPRISE
# ===============================

# list users
@login_required
def company_users_list_view(request, company_id):

    company = get_managed_company_or_403(request, company_id)

    if company is None:
        return render(request, "messaging/forbidden.html")

    users = User.objects.filter(
        company=company
        ).exclude(
            id=request.user.id
        ).exclude(
            role="super_admin"
        )

    return render(request, "accounts/company_users_list.html", {
        "company": company,
        "users": users,
    })


# create user
@login_required
def company_user_create_view(request, company_id):

    company = get_managed_company_or_403(request, company_id)

    if company is None:
        return render(request, "messaging/forbidden.html")

    if request.method == "POST":

        form = CompanyUserCreateForm(request.POST)
        form.instance.company = company

        if form.is_valid():

            user_obj = form.save(commit=False)

            # 🔒 sécurité
            if not request.user.is_super_admin():
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
        form = CompanyUserCreateForm()

    return render(request, "accounts/company_user_form.html", {
        "form": form,
        "company": company,
        "is_edit": False,
    })


# recharge user
@login_required
def company_user_recharge_view(request, company_id, user_id):

    company = get_managed_company_or_403(request, company_id)

    if company is None:
        return render(request, "messaging/forbidden.html")

    target_user = get_object_or_404(User, pk=user_id, company=company)

    if request.method == "POST":

        form = UserRechargeForm(request.POST)

        if form.is_valid():

            amount = form.cleaned_data["amount"]

            if amount <= 0:
                messages.error(request, "Montant invalide.")
                return redirect("company_users_list", company_id=company.id)

            with transaction.atomic():

                company = Company.objects.select_for_update().get(pk=company.pk)
                target_user = User.objects.select_for_update().get(pk=target_user.pk)

                if company.balance < amount:
                    messages.error(request, "Solde insuffisant.")
                    return redirect("company_users_list", company_id=company.id)

                company.balance -= amount
                company.save(update_fields=["balance"])

                target_user.credit_balance += amount
                target_user.save(update_fields=["credit_balance"])

                CompanyTransaction.objects.create(
                    company=company,
                    amount=amount,
                    transaction_type='debit',
                    description=f"Recharge utilisateur {target_user.username}"
                )

                UserCreditTransaction.objects.create(
                    company=company,
                    user=target_user,
                    amount=amount,
                    transaction_type='credit',
                    description="Recharge utilisateur"
                )

            messages.success(request, "Recharge effectuée.")

            return redirect("company_users_list", company_id=company.id)

    else:
        form = UserRechargeForm()

    return render(request, "accounts/user_recharge.html", {
        "form": form,
        "company": company,
        "target_user": target_user,
    })



@login_required
def company_user_update_view(request, company_id, user_id):

    company = get_managed_company_or_403(request, company_id)

    if company is None:
        return render(request, "messaging/forbidden.html")

    user_obj = get_object_or_404(
        User,
        id=user_id,
        company=company
    )

    # 🔥 IMPORTANT : instance
    form = UserForm(request.POST or None, instance=user_obj)

    if request.method == "POST":

        if form.is_valid():

            user = form.save(commit=False)

            # 🔒 sécurité rôle
            if not request.user.is_super_admin():
                user.role = user_obj.role

            # 🔐 mot de passe
            password = form.cleaned_data.get("password")
            if password:
                user.set_password(password)

            user.save()

            messages.success(request, "Utilisateur modifié avec succès.")

            return redirect("company_users_list", company_id=company.id)

        else:
            messages.error(request, "Erreur dans le formulaire.")

    return render(request, "accounts/company_user_form.html", {
        "form": form,  # 🔥 ICI on envoie le form
        "company": company,
        "is_edit": True,
        "target_user": user_obj
    })


# delete user
@login_required
def company_user_delete_view(request, company_id, user_id):

    company = get_managed_company_or_403(request, company_id)

    if company is None:
        return render(request, "messaging/forbidden.html")

    user_obj = get_object_or_404(
        User,
        id=user_id,
        company=company
    )

    # 🔒 sécurité : ne pas supprimer soi-même
    if user_obj == request.user:
        messages.error(request, "Vous ne pouvez pas supprimer votre propre compte.")
        return redirect("company_users_list", company_id=company.id)

    # 🔒 sécurité : ne pas supprimer super admin
    if user_obj.is_super_admin():
        messages.error(request, "Impossible de supprimer un super admin.")
        return redirect("company_users_list", company_id=company.id)

    user_obj.delete()

    messages.success(request, "Utilisateur supprimé avec succès.")

    return redirect("company_users_list", company_id=company.id)



# ===============================
# TOGGLE USER ACTIVE
# ===============================
@login_required
def company_user_toggle_active_view(request, company_id, user_id):

    company = get_managed_company_or_403(request, company_id)

    if company is None:
        return render(request, "messaging/forbidden.html")

    user_obj = get_object_or_404(
        User,
        id=user_id,
        company=company
    )

    # 🔒 sécurité : éviter désactivation super admin
    if user_obj.is_super_admin():
        messages.error(request, "Impossible de désactiver un super admin.")
        return redirect("company_users_list", company_id=company.id)

    # 🔄 toggle actif/inactif
    user_obj.is_active = not user_obj.is_active
    user_obj.save()

    status = "activé" if user_obj.is_active else "désactivé"
    messages.success(request, f"Utilisateur {status} avec succès.")

    return redirect("company_users_list", company_id=company.id)




@login_required
def user_profile_view(request):

    user = request.user

    if request.method == "POST":

        form = UserProfileForm(request.POST, instance=user)

        if form.is_valid():

            user = form.save(commit=False)

            password = form.cleaned_data.get("password")

            if password:
                user.set_password(password)
                update_session_auth_hash(request, user)

            user.save()

            messages.success(request, "Profil mis à jour avec succès")

            return redirect("user_profile")

    else:
        form = UserProfileForm(instance=user)

    return render(request, "accounts/profile.html", {
        "form": form
    })




# company toggle active
@login_required
def company_toggle_active_view(request, pk):

    # 🔒 uniquement super admin
    if not request.user.is_super_admin():
        return redirect("dashboard")

    company = get_object_or_404(Company, pk=pk)

    # 🔒 sécurité : éviter de se bloquer soi-même
    if request.user.company == company:
        messages.error(request, "Vous ne pouvez pas désactiver votre propre entreprise.")
        return redirect("company_list")

    # 🔄 toggle actif / inactif
    company.is_active = not company.is_active
    company.save()

    status = "activée" if company.is_active else "désactivée"

    messages.success(request, f"Entreprise {status} avec succès.")

    return redirect("company_list")
