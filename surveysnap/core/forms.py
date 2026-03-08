from django.contrib.auth.forms import UserCreationForm
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