import openpyxl

import re

from typing import Container

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required

from .models import ContactGroup, Contact
from django.contrib import messages

######################
# GROUPES
######################

# Lister les groupes
@login_required
def contact_groups_list(request):

    groups = ContactGroup.objects.filter(owner=request.user)

    return render(request, "contacts/groups_list.html", {
        "groups": groups
    })


# Créer un groupe
@login_required
def contact_group_create(request):

    if request.method == "POST":

        name = request.POST.get("name")

        ContactGroup.objects.create(
            name=name,
            owner=request.user
        )

        return redirect("contact_groups_list")

    return render(request, "contacts/group_create.html")


# Détail d'un groupe
@login_required
def contact_group_detail(request, group_id):

    group = get_object_or_404(ContactGroup, id=group_id, owner=request.user)

    contacts = group.contacts.all()

    return render(request, "contacts/group_detail.html", {
        "group": group,
        "contacts": contacts
    })


# Modifier un groupe
@login_required
def contact_group_edit(request, group_id):

    group = get_object_or_404(ContactGroup, id=group_id, owner=request.user)

    if request.method == "POST":

        group.name = request.POST.get("name")
        group.description = request.POST.get("description")

        group.save()

        return redirect("contact_groups_list")

    return render(request, "contacts/group_edit.html", {
        "group": group
    })


# Supprimer un groupe
@login_required
def contact_group_delete(request, group_id):

    group = get_object_or_404(ContactGroup, id=group_id, owner=request.user)

    group.delete()

    return redirect("contact_groups_list")



######################
# CONTACTS
######################

# ✅ Ajouter un contact dans un groupe
@login_required
def contact_create(request, group_id):

    group = get_object_or_404(ContactGroup, id=group_id, owner=request.user)

    if request.method == "POST":

        name = request.POST.get("name")
        phone = request.POST.get("phone")
        email = request.POST.get("email")

        # éviter doublon dans le groupe
        Contact.objects.get_or_create(
            group=group,
            phone=phone,
            defaults={
                "name": name,
                "email": email
            }
        )

    return redirect("contact_group_detail", group_id=group.id)


# ✅ Importer contact excel
@login_required
def contacts_import_excel(request, group_id):

    group = get_object_or_404(ContactGroup, id=group_id, owner=request.user)

    if request.method == "POST":

        file = request.FILES.get("file")

        if not file:
            messages.error(request, "Veuillez sélectionner un fichier Excel")
            return redirect("contact_group_detail", group_id=group.id)
        
        workbook = openpyxl.load_workbook(file)
        sheet = workbook.active

        total_rows = 0
        created = 0
        duplicates = []
        invalid = []

        phone_regex = r"^\+225\d{10}$"

        for row in sheet.iter_rows(min_row=2, values_only=True):

            phone = row[0]

            # ignorer les lignes vides
            if phone is None or str(phone).strip() == "":
                continue

            phone = str(phone).strip()
            name = row[1] if len(row) > 1 else ""

            total_rows += 1
            
            # validation du numéro
            if not re.match(phone_regex, phone):
                invalid.append(phone)
                continue

            # vérifier si le contact existe déjà
            if Contact.objects.filter(group=group, phone=phone).exists():
                duplicates.append(phone)
                continue

            Contact.objects.get_or_create(
                group=group,
                phone=phone,
                name=name
            )

            created += 1
    
        return render(request, "contacts/import_result.html", {
            "group": group,
            "total_rows": total_rows,
            "created": created,
            "duplicates": duplicates,
            "invalid": invalid
        })

    return render(request, "contacts/import_excel.html", {
        "group": group
    })



#  ✅ modifier un contact
@login_required
def contact_edit(request, contact_id):

    contact = get_object_or_404(Contact, id=contact_id, group__owner=request.user)

    if request.method == "POST":

        contact.phone = request.POST.get("phone")
        contact.name = request.POST.get("name")
        contact.email = request.POST.get("email")

        contact.save()

        return redirect("contact_group_detail", group_id=contact.group.id)

    return render(request, "contacts/contact_edit.html", {
        "contact": contact
    })

#  ✅ supprimer un contact
@login_required
def contact_delete(request, contact_id):

    contact = get_object_or_404(Contact, id=contact_id, group__owner=request.user)

    group_id = contact.group.id

    contact.delete()

    return redirect("contact_group_detail", group_id=group_id)