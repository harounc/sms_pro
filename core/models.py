from django.db import models
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model

from accounts.models import Company

User = get_user_model()


# ==============================
# TRANSACTION (CENTRAL 💰)
# ==============================
class Transaction(models.Model):

    TRANSACTION_TYPE = (
        ('debit', 'Débit'),
        ('credit', 'Crédit'),
    )

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="core_transactions"   # ✅ CORRIGÉ
    )

    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="user_transactions"
    )

    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    transaction_type = models.CharField(
        max_length=10,
        choices=TRANSACTION_TYPE
    )

    description = models.CharField(
        max_length=255,
        blank=True
    )

    reference = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )

    balance_before = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )

    balance_after = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company']),
            models.Index(fields=['transaction_type']),
            models.Index(fields=['created_at']),
        ]

    def clean(self):

        if self.amount <= 0:
            raise ValidationError("Le montant doit être positif.")

        if self.user and self.user.company != self.company:
            raise ValidationError("Utilisateur invalide pour cette entreprise.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.company.name} - {self.transaction_type} - {self.amount}"


# ==============================
# API LOG
# ==============================
class ApiLog(models.Model):

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="api_logs"
    )

    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    endpoint = models.CharField(max_length=255)

    method = models.CharField(max_length=10, blank=True, null=True)

    request_data = models.TextField()
    response_data = models.TextField()

    status_code = models.IntegerField()

    ip_address = models.GenericIPAddressField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company']),
            models.Index(fields=['status_code']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"{self.endpoint} - {self.status_code}"