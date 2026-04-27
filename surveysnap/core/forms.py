from django.contrib.auth.forms import PasswordResetForm, SetPasswordForm, UserCreationForm
from .models import User
from django import forms


class UserSignupForm(UserCreationForm):
    class Meta:
        model = User
        fields = [
            'email',
            'first_name',
            'last_name',
            'gender',
            'phone_no',
            'role',
        ]

        widgets = {
            'gender': forms.RadioSelect(),
        }
    
class UserLoginForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            "class": "block w-full pl-11 pr-4 h-14 border border-slate-200 bg-white rounded-lg focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none",
        })
    )

    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            "class": "block w-full pl-11 pr-12 h-14 border border-slate-200 bg-white rounded-lg focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none",
        })
    )


class ForgotPasswordForm(PasswordResetForm):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            "class": "block w-full pl-11 pr-4 h-14 border border-slate-200 bg-white rounded-lg focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none",
            "placeholder": "Enter your registered email",
            "autocomplete": "email",
        })
    )

    def clean_email(self):
        email = self.cleaned_data["email"]

        if not User.objects.filter(email__iexact=email, is_active=True).exists():
            raise forms.ValidationError(
                "We couldn't find an active SurveySnap account with that email address."
            )

        return email


class ResetPasswordForm(SetPasswordForm):
    new_password1 = forms.CharField(
        label="New password",
        widget=forms.PasswordInput(attrs={
            "class": "block w-full pl-11 pr-4 h-14 border border-slate-200 bg-white rounded-lg focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none",
            "placeholder": "Create a strong new password",
            "autocomplete": "new-password",
        }),
    )
    new_password2 = forms.CharField(
        label="Confirm password",
        widget=forms.PasswordInput(attrs={
            "class": "block w-full pl-11 pr-4 h-14 border border-slate-200 bg-white rounded-lg focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none",
            "placeholder": "Re-enter your new password",
            "autocomplete": "new-password",
        }),
    )


class RespondentProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = [
            "first_name",
            "last_name",
            "gender",
            "phone_no",
        ]
        widgets = {
            "first_name": forms.TextInput(attrs={
                "class": "w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-slate-900 outline-none transition focus:border-blue-500 focus:ring-4 focus:ring-blue-100",
                "placeholder": "Enter first name",
            }),
            "last_name": forms.TextInput(attrs={
                "class": "w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-slate-900 outline-none transition focus:border-blue-500 focus:ring-4 focus:ring-blue-100",
                "placeholder": "Enter last name",
            }),
            "gender": forms.Select(attrs={
                "class": "w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-slate-900 outline-none transition focus:border-blue-500 focus:ring-4 focus:ring-blue-100",
            }),
            "phone_no": forms.TextInput(attrs={
                "class": "w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-slate-900 outline-none transition focus:border-blue-500 focus:ring-4 focus:ring-blue-100",
                "placeholder": "Enter phone number",
            }),
        }
