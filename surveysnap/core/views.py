from django.shortcuts import render, redirect
from .forms import UserSignupForm, UserLoginForm
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.http import HttpResponse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

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
    next_url = request.POST.get("next") or request.GET.get("next") or ""

    if request.method == "POST":
        form = UserLoginForm(request.POST or None)

        if form.is_valid():
            email = form.cleaned_data["email"]
            password = form.cleaned_data["password"]

            user = authenticate(request, email=email, password=password)

            if user:
                login(request, user)

                if next_url and url_has_allowed_host_and_scheme(
                    next_url,
                    allowed_hosts={request.get_host()},
                    require_https=request.is_secure(),
                ):
                    return redirect(next_url)

                if user.role == "admin":
                    return redirect("admin_dashboard")
                elif user.role == "creator":
                    return redirect("creator_dashboard")
                elif user.role == "respondent":
                    return redirect("respondent_dashboard")

        return render(request, "core/login.html", {"form": form, "next_url": next_url})

    form = UserLoginForm()
    return render(request, "core/login.html", {"form": form, "next_url": next_url})


# =========================
# USER LOGOUT VIEW
# =========================
def userLogoutView(request):
    logout(request)
    return redirect("home")


@csrf_exempt
@require_POST
def userAutoLogoutView(request):
    if request.user.is_authenticated:
        logout(request)
    return HttpResponse(status=204)
