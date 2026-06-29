from contacts.models import ContactGroup

# ==============================
# 📦 GROUPES ACCESSIBLES
# ==============================
def get_user_groups(user):

    # Super admin → tous les groupes
    if user.role == "super_admin":
        return ContactGroup.objects.all()

    # Admin entreprise → tous les groupes de son entreprise
    if user.role == "admin":
        return user.company.contact_groups.all()

    # User normal → seulement ses groupes
    return user.contact_groups.all()


# ==============================
# 🔐 ACCÈS À UN GROUPE
# ==============================
def can_access_group(user, group):

    # Super admin → accès total
    if user.role == "super_admin":
        return True

    # Sécurité entreprise
    if group.company != user.company:
        return False

    # Admin entreprise → accès total entreprise
    if user.role == "admin":
        return True

    # User normal → uniquement ses groupes
    return group.owner == user


# ==============================
# 🔐 ADMIN ENTREPRISE
# ==============================
def is_company_admin(user):
    return user.role == "admin"
