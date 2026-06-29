from django.contrib import messages
from django.contrib.auth import SESSION_KEY, get_user_model, logout
from django.shortcuts import redirect


PUBLIC_PATH_PREFIXES = (
    "/login/",
    "/accounts/login/",
    "/logout/",
    "/admin/",
    "/password-reset/",
    "/reset/",
    "/static/",
)


class CompanyActiveMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):

        if request.path.startswith(PUBLIC_PATH_PREFIXES):
            return self.get_response(request)

        if not request.user.is_authenticated and SESSION_KEY in request.session:
            user_id = request.session.get(SESSION_KEY)
            user = get_user_model().objects.filter(pk=user_id).first()

            if user and not user.is_active:
                logout(request)
                messages.error(request, "Votre compte est désactivé.")
                return redirect("login")

        if request.user.is_authenticated:

            if not request.user.is_active:
                logout(request)
                messages.error(request, "Votre compte est désactivé.")
                return redirect("login")

            company = getattr(request.user, "company", None)

            if company and hasattr(company, "is_active") and not company.is_active:
                logout(request)
                messages.error(request, "Votre entreprise est désactivée.")
                return redirect("login")

        return self.get_response(request)
