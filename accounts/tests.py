from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from accounts.models import Company, CompanyTransaction, User, UserCreditTransaction


class AccountRechargeTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            name="Recharge Co",
            balance=Decimal("100.00"),
        )
        self.super_admin = User.objects.create_superuser(
            username="super",
            password="password",
            email="super@example.com",
        )
        self.admin = User.objects.create_user(
            username="admin",
            password="password",
            company=self.company,
            role="admin",
        )
        self.user = User.objects.create_user(
            username="agent",
            password="password",
            company=self.company,
            role="user",
        )

    def test_super_admin_can_recharge_company_and_transaction_is_recorded(self):
        self.client.force_login(self.super_admin)

        response = self.client.post(
            reverse("company_recharge", args=[self.company.id]),
            {"amount": "50.00"},
        )

        self.assertRedirects(response, reverse("company_list"))
        self.company.refresh_from_db()
        self.assertEqual(self.company.balance, Decimal("150.00"))
        self.assertEqual(CompanyTransaction.objects.count(), 1)
        self.assertEqual(CompanyTransaction.objects.first().transaction_type, "credit")

    def test_company_admin_cannot_recharge_company_directly(self):
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("company_recharge", args=[self.company.id]),
            {"amount": "50.00"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "messaging/forbidden.html")
        self.company.refresh_from_db()
        self.assertEqual(self.company.balance, Decimal("100.00"))
        self.assertEqual(CompanyTransaction.objects.count(), 0)

    def test_company_admin_recharges_user_from_company_balance(self):
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("company_user_recharge", args=[self.company.id, self.user.id]),
            {"amount": "40.00"},
        )

        self.assertRedirects(response, reverse("company_users_list", args=[self.company.id]))
        self.company.refresh_from_db()
        self.user.refresh_from_db()
        self.assertEqual(self.company.balance, Decimal("60.00"))
        self.assertEqual(self.user.credit_balance, Decimal("40.00"))
        self.assertEqual(CompanyTransaction.objects.count(), 1)
        self.assertEqual(UserCreditTransaction.objects.count(), 1)

    def test_user_recharge_with_insufficient_company_balance_does_not_mutate_balances(self):
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("company_user_recharge", args=[self.company.id, self.user.id]),
            {"amount": "150.00"},
        )

        self.assertRedirects(response, reverse("company_users_list", args=[self.company.id]))
        self.company.refresh_from_db()
        self.user.refresh_from_db()
        self.assertEqual(self.company.balance, Decimal("100.00"))
        self.assertEqual(self.user.credit_balance, Decimal("0.00"))
        self.assertEqual(CompanyTransaction.objects.count(), 0)
        self.assertEqual(UserCreditTransaction.objects.count(), 0)


class LoginPageTests(TestCase):
    def test_login_page_uses_local_styles_and_polished_layout(self):
        response = self.client.get(reverse("login"))
        content = response.content.decode("utf-8")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "login-panel")
        self.assertContains(response, "/static/css/tailwind")
        self.assertNotIn("cdn.tailwindcss.com", content)
