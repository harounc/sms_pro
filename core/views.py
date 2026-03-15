from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required


@login_required
def redirect_after_login(request):

    if request.user.role == "admin" and request.user.company is None:
        return redirect("accounts_dashboard")
    else:
        return redirect("dashboard")