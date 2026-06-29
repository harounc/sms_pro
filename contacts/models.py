from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError

from accounts.models import Company


# ==============================
# CONTACT GROUP
# ==============================

class ContactGroup(models.Model):

    name = models.CharField(max_length=150)

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="contact_groups"
    )

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="contact_groups"
    )

    description = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Groupe de contact"
        verbose_name_plural = "Groupes de contacts"

        constraints = [
            models.UniqueConstraint(
                fields=["company", "name"],
                name="unique_group_name_per_company"
            )
        ]

    def clean(self):
        if self.owner.company != self.company:
            raise ValidationError(
                "Le propriétaire doit appartenir à la même entreprise."
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.company.name})"

    @property
    def contacts_count(self):
        return self.contacts.count()


# ==============================
# CONTACT
# ==============================

class Contact(models.Model):

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="contacts"
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="contacts"
    )

    group = models.ForeignKey(
        ContactGroup,
        on_delete=models.CASCADE,
        related_name="contacts"
    )

    name = models.CharField(max_length=150, blank=True)

    phone = models.CharField(max_length=20)

    email = models.EmailField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:

        ordering = ["name"]

        verbose_name = "Contact"
        verbose_name_plural = "Contacts"

        constraints = [
            models.UniqueConstraint(
                fields=["user", "phone"],
                name="unique_phone_per_user"
            )
        ]

        indexes = [
            models.Index(fields=["phone"]),
            models.Index(fields=["company"]),
            models.Index(fields=["user"]),
        ]

    def clean(self):

        if self.group.company != self.company:
            raise ValidationError(
                "Le groupe doit appartenir à la même entreprise."
            )

        if self.user.company != self.company:
            raise ValidationError(
                "Le user doit appartenir à la même entreprise."
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        if self.name:
            return f"{self.name} - {self.phone}"
        return self.phone
