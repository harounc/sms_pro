from django.db import models
from accounts.models import Company


class Transaction(models.Model):

    TRANSACTION_TYPE = (
        ('debit', 'Debit'),
        ('credit', 'Credit'),
    )

    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPE)
    description = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)


class ApiLog(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE)

    endpoint = models.CharField(max_length=255)
    request_data = models.TextField()
    response_data = models.TextField()
    status_code = models.IntegerField()

    created_at = models.DateTimeField(auto_now_add=True)