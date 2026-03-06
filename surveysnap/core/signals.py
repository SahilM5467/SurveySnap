from django.db.models.signals import post_save
from django.dispatch import receiver
from django.template.loader import render_to_string
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from email.mime.image import MIMEImage
from .models import User
import os


@receiver(post_save, sender=User)
def send_welcome_email(sender, instance, created, **kwargs):

    if created:

        email = instance.email
        first_name = instance.first_name
        last_name = instance.last_name

        html_content = render_to_string(
            "emails/welcome_email.html",
            {
                "first_name": first_name,
                "last_name": last_name
            }
        )

        email_message = EmailMultiAlternatives(
            subject="🎉 Welcome to SurveySnap",
            body="Welcome to SurveySnap",
            from_email=settings.EMAIL_HOST_USER,
            to=[email],
        )

        email_message.attach_alternative(html_content, "text/html")

        # Attach Logo
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

        email_message.send(fail_silently=False)