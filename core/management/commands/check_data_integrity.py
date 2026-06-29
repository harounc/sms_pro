import re

from django.core.management.base import BaseCommand, CommandError
from django.db.models import F, Q

from accounts.models import Company, User
from contacts.models import Contact
from messaging.models import Campaign, Message, Sender


PHONE_REGEX = r"^\+225\d{10}$"


class Command(BaseCommand):
    help = "Vérifie les incohérences de données sans modifier la base."

    def add_arguments(self, parser):
        parser.add_argument(
            "--fail-on-issues",
            action="store_true",
            help="Retourne une erreur si au moins une incohérence est détectée.",
        )

    def handle(self, *args, **options):
        checks = [
            ("Entreprises avec solde négatif", self.negative_company_balances),
            ("Utilisateurs avec crédit négatif", self.negative_user_credits),
            ("Utilisateurs entreprise sans entreprise", self.company_users_without_company),
            ("Superusers avec rôle invalide", self.superusers_with_invalid_role),
            ("Super admins rattachés à une entreprise", self.super_admins_with_company),
            ("Contacts avec téléphone invalide", self.invalid_contact_phones),
            ("Contacts hors entreprise", self.contacts_with_company_mismatch),
            ("Campagnes hors entreprise", self.campaigns_with_company_mismatch),
            ("Messages sans titre", self.messages_without_title),
            ("Messages hors entreprise", self.messages_with_company_mismatch),
            ("Expéditeurs avec créateur hors entreprise", self.senders_with_creator_mismatch),
        ]

        total_issues = 0

        for label, check in checks:
            count = check()
            total_issues += count

            if count:
                self.stdout.write(self.style.WARNING(f"{label}: {count}"))
            else:
                self.stdout.write(self.style.SUCCESS(f"{label}: OK"))

        if total_issues:
            message = f"{total_issues} incohérence(s) détectée(s)."
            if options["fail_on_issues"]:
                raise CommandError(message)
            self.stdout.write(self.style.WARNING(message))
            return

        self.stdout.write(self.style.SUCCESS("Aucune incohérence détectée."))

    def negative_company_balances(self):
        return Company.objects.filter(balance__lt=0).count()

    def negative_user_credits(self):
        return User.objects.filter(credit_balance__lt=0).count()

    def company_users_without_company(self):
        return User.objects.filter(
            role__in=["admin", "user"],
            company__isnull=True,
            is_superuser=False,
        ).count()

    def superusers_with_invalid_role(self):
        return User.objects.filter(is_superuser=True).exclude(role="super_admin").count()

    def super_admins_with_company(self):
        return User.objects.filter(role="super_admin", company__isnull=False).count()

    def invalid_contact_phones(self):
        return sum(
            1
            for phone in Contact.objects.values_list("phone", flat=True)
            if not re.fullmatch(PHONE_REGEX, phone or "")
        )

    def contacts_with_company_mismatch(self):
        return Contact.objects.filter(
            Q(group__company_id__isnull=False) & ~Q(group__company_id=F("company_id"))
            | Q(user__company_id__isnull=False) & ~Q(user__company_id=F("company_id"))
        ).count()

    def campaigns_with_company_mismatch(self):
        return Campaign.objects.filter(~Q(user__company_id=F("company_id"))).count()

    def messages_without_title(self):
        return Message.objects.filter(Q(title__isnull=True) | Q(title="")).count()

    def messages_with_company_mismatch(self):
        return Message.objects.filter(
            ~Q(user__company_id=F("company_id"))
            | Q(campaign__isnull=False) & ~Q(campaign__company_id=F("company_id"))
        ).count()

    def senders_with_creator_mismatch(self):
        return Sender.objects.filter(
            created_by__isnull=False
        ).exclude(
            created_by__company_id=F("company_id")
        ).count()
