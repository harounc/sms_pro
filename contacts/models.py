from django.db import models
from django.conf import settings


class ContactGroup(models.Model):

    name = models.CharField(max_length=150)

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="contact_groups"
    )

    description = models.TextField(
        blank=True,
        null=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Groupe de contact"
        verbose_name_plural = "Groupes de contacts"

    def __str__(self):
        return f"{self.name} ({self.owner})"

    @property
    def contacts_count(self):
        return self.contacts.count()



class Contact(models.Model):

    group = models.ForeignKey(
        ContactGroup,
        on_delete=models.CASCADE,
        related_name="contacts"
    )

    name = models.CharField(
        max_length=150,
        blank=True
    )

    phone = models.CharField(
        max_length=20
    )

    email = models.EmailField(
        blank=True,
        null=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:

        ordering = ["name"]

        verbose_name = "Contact"
        verbose_name_plural = "Contacts"

        # Empêche les doublons dans un groupe
        unique_together = ("group", "phone")

        indexes = [
            models.Index(fields=["phone"]),
        ]

    def __str__(self):
        if self.name:
            return f"{self.name} - {self.phone}"
        return self.phone