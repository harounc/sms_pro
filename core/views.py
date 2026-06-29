from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required


@login_required
def redirect_after_login(request):

    user = request.user

    # 🔥 SUPER ADMIN (plateforme)
    if user.is_super_admin():
        return redirect("accounts_dashboard")

    # 🔥 ADMIN ENTREPRISE
    if user.is_admin():
        return redirect("dashboard")

    # 🔥 USER ENTREPRISE
    if user.is_user():
        return redirect("dashboard")

    # 🔒 fallback sécurité
    return redirect("login")