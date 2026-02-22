from django.db import models
from accounts.models import User, Company
from .managers import CompanyManager


# ==============================
# CONTACT
# ==============================

class Contact(models.Model):

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    company = models.ForeignKey(Company, on_delete=models.CASCADE)

    name = models.CharField(max_length=150)
    phone = models.CharField(max_length=20)

    created_at = models.DateTimeField(auto_now_add=True)

    objects = CompanyManager()

    class Meta:
        unique_together = ('company', 'phone')
        indexes = [
            models.Index(fields=['company', 'phone']),
        ]

    def __str__(self):
        return f"{self.name} - {self.phone}"


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

    objects = CompanyManager()

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'status']),
            # models.Index(fields=['created_at']), # ch
        ]

    def __str__(self):
        return f"{self.name} - {self.company.name}"


# ==============================
# MESSAGE
# ==============================

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

    phone = models.CharField(max_length=20)
    message = models.TextField()

    message_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)

    cost = models.DecimalField(max_digits=8, decimal_places=3, default=0)

    scheduled_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    
    objects = CompanyManager()

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'status']),
            models.Index(fields=['sent_at']),
            models.Index(fields=['scheduled_at']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"{self.phone} - {self.status}"