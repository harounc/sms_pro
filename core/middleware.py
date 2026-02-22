from django.shortcuts import redirect
from django.urls import reverse


class CompanyActiveMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):

        # On laisse passer la page login et admin
        if request.path.startswith("/login") or request.path.startswith("/admin"):
            return self.get_response(request)

        if request.user.is_authenticated:

            # Vérifie que l'utilisateur a bien une company
            company = getattr(request.user, "company", None)

            if company:

                # Vérifie que company a bien le champ is_active
                if hasattr(company, "is_active") and not company.is_active:
                    return redirect("login")

        return self.get_response(request)