from django.urls import path
from .views import *

urlpatterns = [

    path("groups/", contact_groups_list, name="contact_groups_list"),

    path("groups/create/", contact_group_create, name="contact_group_create"),

    path("groups/<int:group_id>/", contact_group_detail, name="contact_group_detail"),

    path("groups/<int:group_id>/edit/", contact_group_edit, name="contact_group_edit"),

    path("groups/<int:group_id>/delete/", contact_group_delete, name="contact_group_delete"),


    # 📊 statistiques groupe
    path("groups-stats/", contact_group_stats, name="contact_group_stats"),
    

    # ✅ ajouter contact
    path("groups/<int:group_id>/contacts/create/", contact_create, name="contact_create"),

    # importer contact
    path("group/<int:group_id>/import-excel/", contacts_import_excel, name="contacts_import_excel"),

    # ✅ modifier contact
    path("contacts/<int:contact_id>/edit/", contact_edit, name="contact_edit"),

    # ✅ supprimer contact
    path("contacts/<int:contact_id>/delete/", contact_delete, name="contact_delete"),

]