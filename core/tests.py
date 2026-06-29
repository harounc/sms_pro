from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.urls import reverse

from accounts.models import Company, User
from contacts.models import Contact, ContactGroup


class GlobalPermissionTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Permissions Co")
        self.admin = User.objects.create_user(
            username="perm-admin",
            password="password",
            company=self.company,
            role="admin",
        )
        self.user = User.objects.create_user(
            username="perm-user",
            password="password",
            company=self.company,
            role="user",
        )
        self.super_admin = User.objects.create_superuser(
            username="perm-super",
            password="password",
            email="super@example.com",
        )

    def test_login_url_is_canonical_root_login(self):
        self.assertEqual(reverse("login"), "/login/")
        response = self.client.get(reverse("login"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Connexion")

    def test_redirect_after_login_routes_by_role(self):
        self.client.force_login(self.super_admin)
        response = self.client.get(reverse("redirect_after_login"))
        self.assertRedirects(response, reverse("accounts_dashboard"))

        self.client.force_login(self.admin)
        response = self.client.get(reverse("redirect_after_login"))
        self.assertRedirects(response, reverse("dashboard"))

        self.client.force_login(self.user)
        response = self.client.get(reverse("redirect_after_login"))
        self.assertRedirects(response, reverse("dashboard"))

    def test_inactive_company_is_logged_out_and_redirected_to_login(self):
        self.company.is_active = False
        self.company.save(update_fields=["is_active"])
        self.client.force_login(self.admin)

        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith(reverse("login")))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_inactive_user_is_logged_out_and_redirected_to_login(self):
        self.client.force_login(self.user)
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])

        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith(reverse("login")))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_login_refuses_inactive_company(self):
        self.company.is_active = False
        self.company.save(update_fields=["is_active"])

        response = self.client.post(reverse("login"), {
            "username": "perm-admin",
            "password": "password",
        })

        self.assertRedirects(response, reverse("login"))
        self.assertNotIn("_auth_user_id", self.client.session)


class DataIntegrityCommandTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Integrity Co")
        self.user = User.objects.create_user(
            username="integrity-user",
            password="password",
            company=self.company,
            role="user",
        )
        self.group = ContactGroup.objects.create(
            name="Clients",
            company=self.company,
            owner=self.user,
        )

    def test_check_data_integrity_reports_no_issues_for_clean_data(self):
        out = StringIO()

        call_command("check_data_integrity", stdout=out)

        self.assertIn("Aucune incohérence détectée.", out.getvalue())

    def test_check_data_integrity_can_fail_on_invalid_contact_phone(self):
        Contact.objects.create(
            company=self.company,
            user=self.user,
            group=self.group,
            phone="0700000000",
        )

        with self.assertRaises(CommandError):
            call_command("check_data_integrity", "--fail-on-issues", stdout=StringIO())
