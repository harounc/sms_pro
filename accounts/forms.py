from django import forms
from django.core.exceptions import ValidationError
from .models import Company, User
from decimal import Decimal


# =====================================================
# FORMULAIRE GLOBAL UTILISATEUR (🔥 MANQUAIT)
# =====================================================

class UserForm(forms.ModelForm):

    password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={
            "class": "w-full border rounded-lg p-3",
            "placeholder": "Laisser vide pour ne pas changer"
        }),
        label="Mot de passe"
    )

    class Meta:
        model = User
        fields = [
            "username",
            "email",
            "first_name",
            "last_name",
            "role",
            "is_active"
        ]

        widgets = {
            "username": forms.TextInput(attrs={'class': 'w-full px-3 py-2 border rounded'}),
            "email": forms.EmailInput(attrs={'class': 'w-full px-3 py-2 border rounded'}),
            "first_name": forms.TextInput(attrs={'class': 'w-full px-3 py-2 border rounded'}),
            "last_name": forms.TextInput(attrs={'class': 'w-full px-3 py-2 border rounded'}),
            "role": forms.Select(attrs={'class': 'w-full px-3 py-2 border rounded'}),
            "is_active": forms.CheckboxInput(attrs={'class': 'rounded'}),
        }

    def clean_email(self):
        email = self.cleaned_data.get("email")

        if email:
            qs = User.objects.filter(email=email).exclude(pk=self.instance.pk)

            if qs.exists():
                raise ValidationError("Cet email est déjà utilisé.")

        return email

    def save(self, commit=True):
        user = super().save(commit=False)

        password = self.cleaned_data.get("password")

        if password:
            user.set_password(password)

        if commit:
            user.save()

        return user


# =====================================================
# FORMULAIRE CREATION UTILISATEUR ENTREPRISE
# =====================================================

class CompanyUserCreateForm(forms.ModelForm):

    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-3 py-2 border rounded'
        }),
        required=False,  # 🔥 devient optionnel
        label="Mot de passe"
    )

    class Meta:
        model = User
        fields = [
            'username',
            'email',
            'first_name',
            'last_name',
            'role',
            'is_active'
        ]

    def clean_username(self):
        username = self.cleaned_data.get("username")
        company = self.instance.company

        if company and User.objects.filter(username=username, company=company).exists():
            raise ValidationError("Ce nom d'utilisateur existe déjà dans cette entreprise.")

        return username

    def clean_email(self):
        email = self.cleaned_data.get("email")

        if email and User.objects.filter(email=email).exists():
            raise ValidationError("Cet email est déjà utilisé.")

        return email

    def clean_role(self):
        role = self.cleaned_data.get("role")

        if role == "super_admin":
            raise ValidationError("Impossible de créer un super admin ici.")

        return role

    def save(self, commit=True):
        user = super().save(commit=False)

        password = self.cleaned_data.get('password')

        # 🔥 génération automatique si vide
        if not password and user.company:
            year = user.company.created_at.year
            password = f"{user.company.name}@{year}"

        user.set_password(password)

        if commit:
            user.save()

        return user


# =====================================================
# FORMULAIRE MODIFICATION UTILISATEUR
# =====================================================

class CompanyUserUpdateForm(forms.ModelForm):

    password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-3 py-2 border rounded',
            'placeholder': 'Laisser vide pour ne pas modifier'
        }),
        label="Mot de passe"
    )

    class Meta:
        model = User
        fields = [
            'username',
            'email',
            'first_name',
            'last_name',
            'role',
            'is_active'
        ]

    def clean_username(self):
        username = self.cleaned_data.get("username")
        company = self.instance.company

        qs = User.objects.filter(username=username, company=company)

        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)

        if qs.exists():
            raise ValidationError("Ce nom d'utilisateur existe déjà dans cette entreprise.")

        return username

    def clean_email(self):
        email = self.cleaned_data.get("email")

        if email:
            qs = User.objects.filter(email=email)

            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)

            if qs.exists():
                raise ValidationError("Cet email est déjà utilisé.")

        return email

    def clean_role(self):
        role = self.cleaned_data.get("role")

        if role == "super_admin":
            raise ValidationError("Modification vers super admin interdite.")

        return role

    def save(self, commit=True):
        user = super().save(commit=False)

        password = self.cleaned_data.get('password')

        if password:
            user.set_password(password)

        if commit:
            user.save()

        return user


# =====================================================
# FORMULAIRE ENTREPRISE
# =====================================================

class CompanyForm(forms.ModelForm):

    class Meta:
        model = Company
        fields = ['name', 'balance', 'is_active']

    def clean_name(self):
        name = self.cleaned_data.get("name")

        if Company.objects.filter(name=name).exclude(pk=self.instance.pk).exists():
            raise ValidationError("Cette entreprise existe déjà.")

        return name


# =====================================================
# RECHARGE ENTREPRISE
# =====================================================

class RechargeForm(forms.Form):

    amount = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal("1.00"),
        widget=forms.NumberInput(attrs={
            "class": "w-full border rounded-lg p-3",
            "placeholder": "Ex: 5000"
        }),
        label="Montant"
    )


# =====================================================
# RECHARGE UTILISATEUR
# =====================================================

class UserRechargeForm(forms.Form):

    amount = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal("1.00"),
        widget=forms.NumberInput(attrs={
            "class": "w-full border rounded-lg p-3",
            "placeholder": "Ex: 1000"
        }),
        label="Montant"
    )


# =====================================================
# PROFIL UTILISATEUR
# =====================================================

class UserProfileForm(forms.ModelForm):

    password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-3 py-2 border rounded',
            'placeholder': 'Laisser vide pour ne pas changer'
        }),
        label="Nouveau mot de passe"
    )

    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "email"]

    def clean_email(self):
        email = self.cleaned_data.get("email")

        if email:
            qs = User.objects.filter(email=email).exclude(pk=self.instance.pk)

            if qs.exists():
                raise ValidationError("Cet email est déjà utilisé.")

        return email

    def save(self, commit=True):
        user = super().save(commit=False)

        password = self.cleaned_data.get("password")

        if password:
            user.set_password(password)

        if commit:
            user.save()

        return user