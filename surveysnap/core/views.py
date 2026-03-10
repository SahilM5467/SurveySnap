from django.shortcuts import render, redirect
from .forms import UserSignupForm, UserLoginForm
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages

def homeView(request):
    return render(request, "core/home.html", {
        "show_home_navbar": True
    })

def featuresView(request):
    return render(request, "core/features.html")

def aboutView(request):
    return render(request, "core/about.html")

def contactView(request):
    return render(request, "core/contact.html")


# =========================
# USER SIGNUP VIEW
# =========================
def userSignupView(request):

    if request.method == "POST":
        form = UserSignupForm(request.POST)

        if form.is_valid():
            form.save()

            messages.success(
                request,
                "Account created successfully! Please login."
            )

            return redirect("login")

        return render(request, "core/signup.html", {"form": form})

    form = UserSignupForm()
    return render(request, "core/signup.html", {"form": form})


# =========================
# USER LOGIN VIEW
# =========================
def userLoginView(request):
    if request.method == "POST":
        form = UserLoginForm(request.POST or None)

        if form.is_valid():
            email = form.cleaned_data["email"]
            password = form.cleaned_data["password"]

            user = authenticate(request, email=email, password=password)

            if user:
                login(request, user)

                if user.role == "admin":
                    return redirect("admin_dashboard")
                elif user.role == "creator":
                    return redirect("creator_dashboard")
                elif user.role == "respondent":
                    return redirect("respondent_dashboard")

        return render(request, "core/login.html", {"form": form})

    form = UserLoginForm()
    return render(request, "core/login.html", {"form": form})


# =========================
# USER LOGOUT VIEW
# =========================
def userLogoutView(request):
    logout(request)
    return redirect("home")