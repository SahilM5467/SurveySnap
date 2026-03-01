from django.shortcuts import render, redirect
from .forms import UserSignupForm, UserLoginForm
from django.contrib.auth import authenticate, login, logout
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.template.loader import render_to_string
from email.mime.image import MIMEImage
import os


def homeView(request):
    return render(request, "core/home.html", {
        "show_home_navbar": True
    })


# =========================
# USER SIGNUP VIEW
# =========================
def userSignupView(request):
    if request.method == "POST":
        form = UserSignupForm(request.POST or None)

        if form.is_valid():
            user = form.save()
            email = form.cleaned_data['email']
            user_name = user.email   # or user.username if available

            # Render HTML Email Template
            html_content = render_to_string(
                "emails/welcome_email.html",
                {"user_name": user_name}
            )

            email_message = EmailMultiAlternatives(
                subject="🎉 Welcome to SurveySnap",
                body="Thank you for registering with SurveySnap.",
                from_email=settings.EMAIL_HOST_USER,
                to=[email],
            )

            # Attach HTML version
            email_message.attach_alternative(html_content, "text/html")

            # =========================
            # Attach Logo (Inline Image)
            # =========================
            logo_path = os.path.join(
                settings.BASE_DIR,
                "static/images/SurveySnap-Logo.png"
            )

            if os.path.exists(logo_path):
                with open(logo_path, "rb") as img:
                    mime_image = MIMEImage(img.read())
                    mime_image.add_header("Content-ID", "<logo_image>")
                    mime_image.add_header(
                        "Content-Disposition",
                        "inline",
                        filename="SurveySnap-Logo.png"
                    )
                    email_message.attach(mime_image)

            # =========================
            # Attach PDF File
            # =========================
            pdf_path = os.path.join(
                settings.BASE_DIR,
                "static/docs/SurveySnap_Welcome_Guide.pdf"
            )

            if os.path.exists(pdf_path):
                with open(pdf_path, "rb") as pdf:
                    email_message.attach(
                        "SurveySnap_Welcome_Guide.pdf",
                        pdf.read(),
                        "application/pdf"
                    )

            # Send Email
            email_message.send(fail_silently=False)

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