from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from openpyxl import Workbook

from accounts.models import Company, User
from contacts.models import Contact, ContactGroup


def make_excel(rows):
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["phone", "name", "email"])
    for row in rows:
        sheet.append(row)

    buffer = BytesIO()
    workbook.save(buffer)
    buffer.seek(0)

    return SimpleUploadedFile(
        "contacts.xlsx",
        buffer.read(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


class ContactImportTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Contacts Co")
        self.admin = User.objects.create_user(
            username="contacts-admin",
            password="password",
            company=self.company,
            role="admin",
        )
        self.group = ContactGroup.objects.create(
            name="Clients",
            company=self.company,
            owner=self.admin,
        )
        self.client.force_login(self.admin)

    def test_import_excel_reports_created_duplicates_and_invalid(self):
        Contact.objects.create(
            company=self.company,
            user=self.admin,
            group=self.group,
            phone="+2250700000001",
            name="Existing",
        )
        upload = make_excel([
            ["+2250700000002", "Alice", "alice@example.com"],
            ["+2250700000001", "Duplicate", "duplicate@example.com"],
            ["0700000000", "Invalid", "invalid@example.com"],
        ])

        response = self.client.post(
            reverse("contacts_import_excel", args=[self.group.id]),
            {"file": upload},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Contact.objects.filter(group=self.group).count(), 2)
        self.assertContains(response, "Importé")
        self.assertContains(response, "Doublon")
        self.assertContains(response, "Invalide")

    def test_contact_create_rejects_invalid_phone(self):
        response = self.client.post(
            reverse("contact_create", args=[self.group.id]),
            {"phone": "0700000000", "name": "Bad"},
        )

        self.assertRedirects(response, reverse("contact_group_detail", args=[self.group.id]))
        self.assertEqual(Contact.objects.count(), 0)

    def test_user_cannot_access_group_from_other_company(self):
        other_company = Company.objects.create(name="Other Co")
        other_user = User.objects.create_user(
            username="other-admin",
            password="password",
            company=other_company,
            role="admin",
        )
        other_group = ContactGroup.objects.create(
            name="Other Clients",
            company=other_company,
            owner=other_user,
        )

        response = self.client.get(reverse("contact_group_detail", args=[other_group.id]))

        self.assertEqual(response.status_code, 404)

    def test_group_create_rejects_duplicate_name(self):
        response = self.client.post(
            reverse("contact_group_create"),
            {"name": "Clients", "description": "Duplicate"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Un groupe avec ce nom existe déjà.")
        self.assertEqual(ContactGroup.objects.filter(company=self.company).count(), 1)

    def test_user_without_company_cannot_create_group(self):
        super_admin = User.objects.create_user(
            username="platform-admin",
            password="password",
            role="super_admin",
        )
        self.client.force_login(super_admin)

        response = self.client.get(reverse("contact_group_create"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "messaging/forbidden.html")

    def test_group_delete_requires_post(self):
        response = self.client.get(reverse("contact_group_delete", args=[self.group.id]))

        self.assertRedirects(response, reverse("contact_groups_list"))
        self.assertTrue(ContactGroup.objects.filter(id=self.group.id).exists())

    def test_group_delete_with_post_removes_group(self):
        response = self.client.post(reverse("contact_group_delete", args=[self.group.id]))

        self.assertRedirects(response, reverse("contact_groups_list"))
        self.assertFalse(ContactGroup.objects.filter(id=self.group.id).exists())

    def test_contact_create_rejects_duplicate_phone_for_same_user(self):
        other_group = ContactGroup.objects.create(
            name="Prospects",
            company=self.company,
            owner=self.admin,
        )
        Contact.objects.create(
            company=self.company,
            user=self.admin,
            group=other_group,
            phone="+2250700000009",
            name="Existing",
        )

        response = self.client.post(
            reverse("contact_create", args=[self.group.id]),
            {"phone": "+2250700000009", "name": "Duplicate"},
        )

        self.assertRedirects(response, reverse("contact_group_detail", args=[self.group.id]))
        self.assertEqual(Contact.objects.filter(user=self.admin, phone="+2250700000009").count(), 1)

    def test_contact_delete_requires_post(self):
        contact = Contact.objects.create(
            company=self.company,
            user=self.admin,
            group=self.group,
            phone="+2250700000010",
        )

        response = self.client.get(reverse("contact_delete", args=[contact.id]))

        self.assertRedirects(response, reverse("contact_group_detail", args=[self.group.id]))
        self.assertTrue(Contact.objects.filter(id=contact.id).exists())

    def test_contact_delete_with_post_removes_contact(self):
        contact = Contact.objects.create(
            company=self.company,
            user=self.admin,
            group=self.group,
            phone="+2250700000011",
        )

        response = self.client.post(reverse("contact_delete", args=[contact.id]))

        self.assertRedirects(response, reverse("contact_group_detail", args=[self.group.id]))
        self.assertFalse(Contact.objects.filter(id=contact.id).exists())
