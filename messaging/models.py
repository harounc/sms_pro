from django.db import models
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from accounts.models import Company

User = get_user_model()


# ==============================
# CAMPAIGN
# ==============================
class Campaign(models.Model):

    STATUS_CHOICES = (
        ('draft', 'Brouillon'),
        ('scheduled', 'Programmée'),
        ('sent', 'Envoyée'),
        ('cancelled', 'Annulée'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    company = models.ForeignKey(Company, on_delete=models.CASCADE)

    name = models.CharField(max_length=200)
    message = models.TextField()

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft'
    )

    scheduled_at = models.DateTimeField(null=True, blank=True)

    total_recipients = models.IntegerField(default=0)
    total_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'status']),
        ]

    def clean(self):
        if self.user.company != self.company:
            raise ValidationError("Utilisateur et entreprise incohérents")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} - {self.company.name}"


class Message(models.Model):

    TYPE_CHOICES = (
        ('simple', 'Simple'),
        ('campaign', 'Campaign'),
    )

    STATUS_CHOICES = (
        ('scheduled', 'Scheduled'),
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    company = models.ForeignKey(Company, on_delete=models.CASCADE)

    campaign = models.ForeignKey(
        Campaign,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='messages'
    )

    title = models.CharField(max_length=255)

    phone = models.CharField(max_length=20)
    message = models.TextField()

    message_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)

    cost = models.DecimalField(max_digits=8, decimal_places=3, default=0)

    scheduled_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'status']),
            models.Index(fields=['sent_at']),
            models.Index(fields=['scheduled_at']),
            models.Index(fields=['message_type']),
            models.Index(fields=['title']),
        ]

    def clean(self):

        if self.user.company != self.company:
            raise ValidationError("Utilisateur et entreprise incohérents")

        if self.campaign and self.campaign.company != self.company:
            raise ValidationError("Campagne invalide pour cette entreprise")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.title} | {self.phone} | {self.status}"

# ==============================
# SENDER
# ==============================
class Sender(models.Model):

    STATUS_CHOICES = [
        ('pending', 'En attente'),
        ('approved', 'Approuvé'),
        ('rejected', 'Refusé'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE)

    name = models.CharField(max_length=15)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_senders"
    )

    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_senders"
    )

    approved_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["company", "name"],
                name="unique_sender_per_company"
            )
        ]

    def clean(self):
        if self.created_by and self.created_by.company != self.company:
            raise ValidationError("Créateur invalide")

    def save(self, *args, **kwargs):
        self.name = self.name.upper()
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name
