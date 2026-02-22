from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError


# ==============================
# COMPANY
# ==============================

class Company(models.Model):
    name = models.CharField(max_length=255)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

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
        related_name='users'
    )

    ROLE_CHOICES = (
        ('admin', 'Admin'),
        ('user', 'User'),
    )

    role = models.CharField(
        max_length=10,
        choices=ROLE_CHOICES,
        default='user'
    )

    class Meta:
        indexes = [
            models.Index(fields=['company']),
        ]

    def clean(self):
        # Si c’est un user normal → il doit avoir une entreprise
        if self.role == "user" and not self.company:
            raise ValidationError(
                "Un utilisateur normal doit appartenir à une entreprise."
            )

    def __str__(self):
        return self.username