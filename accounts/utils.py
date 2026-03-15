from django.shortcuts import get_object_or_404
from .models import Company


def get_managed_company_or_forbidden(request, company_id):

    if request.user.role != "admin":
        return None

    if request.user.company is None:
        return get_object_or_404(Company, pk=company_id)

    if request.user.company_id == company_id:
        return request.user.company

    return None