from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError


# ==============================
# COMPANY
# ==============================

class Company(models.Model):

    name = models.CharField(max_length=255, unique=True)

    balance = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


# ==============================
# USER
# ==============================

class User(AbstractUser):

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="users"
    )

    ROLE_CHOICES = (
        ("admin", "Admin"),
        ("user", "User"),
    )

    role = models.CharField(
        max_length=10,
        choices=ROLE_CHOICES,
        default="user"
    )

    credit_balance = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )

    class Meta:
        indexes = [
            models.Index(fields=["company"]),
        ]

        constraints = [
            models.UniqueConstraint(
                fields=["username", "company"],
                name="unique_username_per_company"
            )
        ]

    def clean(self):

        # Un user normal doit appartenir à une entreprise
        if self.role == "user" and not self.company:
            raise ValidationError(
                "Un utilisateur normal doit appartenir à une entreprise."
            )

    def __str__(self):
        if self.company:
            return f"{self.username} ({self.company.name})"
        return self.username


# ==============================
# COMPANY TRANSACTION
# ==============================

class CompanyTransaction(models.Model):

    TRANSACTION_TYPES = (
        ("credit", "Recharge"),
        ("debit", "Débit SMS"),
    )

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="transactions"
    )

    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    transaction_type = models.CharField(
        max_length=10,
        choices=TRANSACTION_TYPES
    )

    description = models.CharField(
        max_length=255,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.company.name} - {self.transaction_type} - {self.amount}"


# ==============================
# USER CREDIT TRANSACTION
# ==============================

class UserCreditTransaction(models.Model):

    TRANSACTION_TYPES = (
        ("credit", "Crédit"),
        ("debit", "Débit"),
    )

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="user_credit_transactions"
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="credit_transactions"
    )

    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    transaction_type = models.CharField(
        max_length=10,
        choices=TRANSACTION_TYPES
    )

    description = models.CharField(
        max_length=255,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username} - {self.transaction_type} - {self.amount}"