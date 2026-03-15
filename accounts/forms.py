from django import forms
from .models import Company, User


# =====================================================
# FORMULAIRE CREATION UTILISATEUR ENTREPRISE
# =====================================================

class CompanyUserCreateForm(forms.ModelForm):

    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-3 py-2 border rounded'
        }),
        required=True,
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

        widgets = {
            'username': forms.TextInput(attrs={'class': 'w-full px-3 py-2 border rounded'}),
            'email': forms.EmailInput(attrs={'class': 'w-full px-3 py-2 border rounded'}),
            'first_name': forms.TextInput(attrs={'class': 'w-full px-3 py-2 border rounded'}),
            'last_name': forms.TextInput(attrs={'class': 'w-full px-3 py-2 border rounded'}),
            'role': forms.Select(attrs={'class': 'w-full px-3 py-2 border rounded'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'rounded'}),
        }

    # =====================================================
    # VALIDATION USERNAME PAR ENTREPRISE
    # =====================================================

    def clean_username(self):

        username = self.cleaned_data.get("username")

        company = self.instance.company

        if company and User.objects.filter(
                username=username,
                company=company
        ).exists():

            raise forms.ValidationError(
                "Ce nom d'utilisateur existe déjà dans cette entreprise."
            )

        return username

    # =====================================================
    # VALIDATION EMAIL
    # =====================================================

    def clean_email(self):

        email = self.cleaned_data.get("email")

        if email:

            if User.objects.filter(email=email).exists():

                raise forms.ValidationError(
                    "Cet email est déjà utilisé."
                )

        return email

    # =====================================================
    # SAVE
    # =====================================================

    def save(self, commit=True):

        user = super().save(commit=False)

        password = self.cleaned_data.get('password')

        if password:
            user.set_password(password)

        if commit:
            user.save()

        return user


# =====================================================
# FORMULAIRE MODIFICATION UTILISATEUR
# =====================================================

class CompanyUserUpdateForm(forms.ModelForm):

    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-3 py-2 border rounded'
        }),
        required=False,
        label="Mot de passe (laisser vide pour ne pas modifier)"
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

        widgets = {
            'username': forms.TextInput(attrs={'class': 'w-full px-3 py-2 border rounded'}),
            'email': forms.EmailInput(attrs={'class': 'w-full px-3 py-2 border rounded'}),
            'first_name': forms.TextInput(attrs={'class': 'w-full px-3 py-2 border rounded'}),
            'last_name': forms.TextInput(attrs={'class': 'w-full px-3 py-2 border rounded'}),
            'role': forms.Select(attrs={'class': 'w-full px-3 py-2 border rounded'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'rounded'}),
        }

    # =====================================================
    # VALIDATION USERNAME
    # =====================================================

    def clean_username(self):

        username = self.cleaned_data.get("username")

        company = self.instance.company

        qs = User.objects.filter(
            username=username,
            company=company
        )

        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)

        if qs.exists():

            raise forms.ValidationError(
                "Ce nom d'utilisateur existe déjà dans cette entreprise."
            )

        return username

    # =====================================================
    # VALIDATION EMAIL
    # =====================================================

    def clean_email(self):

        email = self.cleaned_data.get("email")

        if email:

            qs = User.objects.filter(email=email)

            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)

            if qs.exists():

                raise forms.ValidationError(
                    "Cet email est déjà utilisé."
                )

        return email

    # =====================================================
    # SAVE
    # =====================================================

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

        fields = [
            'name',
            'balance',
            'is_active'
        ]

        widgets = {
            'name': forms.TextInput(attrs={'class': 'w-full px-3 py-2 border rounded'}),
            'balance': forms.NumberInput(attrs={'class': 'w-full px-3 py-2 border rounded'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'rounded'}),
        }


# =====================================================
# RECHARGE ENTREPRISE
# =====================================================

class RechargeForm(forms.Form):

    amount = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'w-full px-3 py-2 border rounded'
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
        widget=forms.NumberInput(attrs={
            'class': 'w-full px-3 py-2 border rounded'
        }),
        label="Montant"
    )


# =====================================================
# PROFIL UTILISATEUR
# =====================================================

class UserProfileForm(forms.ModelForm):

    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'w-full px-3 py-2 border rounded'}),
        required=False,
        label="Nouveau mot de passe"
    )

    class Meta:
        model = User
        fields = [
            "username",
            "first_name",
            "last_name",
            "email"
        ]

        widgets = {
            "username": forms.TextInput(attrs={'class': 'w-full px-3 py-2 border rounded'}),
            "first_name": forms.TextInput(attrs={'class': 'w-full px-3 py-2 border rounded'}),
            "last_name": forms.TextInput(attrs={'class': 'w-full px-3 py-2 border rounded'}),
            "email": forms.EmailInput(attrs={'class': 'w-full px-3 py-2 border rounded'}),
        }

    def save(self, commit=True):

        user = super().save(commit=False)

        password = self.cleaned_data.get("password")

        if password:
            user.set_password(password)

        if commit:
            user.save()

        return user