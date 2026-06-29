import random
import string

from django.shortcuts import get_object_or_404
from django.core.exceptions import PermissionDenied
from .models import Company


# Company management utilities
def get_managed_company_or_403(request, company_id):
    """
    Retourne une entreprise si l'utilisateur a le droit
    sinon lève PermissionDenied
    """

    user = request.user

    # 🔥 SUPER ADMIN → accès total
    if user.role == "super_admin":
        return get_object_or_404(Company, pk=company_id)

    # 🔥 ADMIN ENTREPRISE → uniquement sa société
    if user.role == "admin":
        if user.company_id == company_id:
            return user.company

        raise PermissionDenied("Accès refusé à cette entreprise.")

    # 🔥 USER → aucun accès
    raise PermissionDenied("Vous n'avez pas les permissions.")



# Password generation utilities
def generate_password(length=10):
    """
    Génère un mot de passe sécurisé aléatoire
    """

    characters = string.ascii_letters + string.digits

    return ''.join(random.choice(characters) for _ in range(length))