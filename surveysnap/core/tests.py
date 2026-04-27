from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .models import User


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    PASSWORD_RESET_TIMEOUT=3600,
)
class ForgotPasswordFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="jane@example.com",
            password="OldPassword@123",
            first_name="Jane",
            last_name="Doe",
            role="creator",
        )
        mail.outbox = []

    def test_password_reset_request_sends_email_for_registered_user(self):
        response = self.client.post(
            reverse("password_reset"),
            {"email": self.user.email},
        )

        self.assertRedirects(response, reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Reset your SurveySnap password", mail.outbox[0].subject)
        self.assertIn("/reset/", mail.outbox[0].body)

    def test_password_reset_request_rejects_unknown_email(self):
        response = self.client.post(
            reverse("password_reset"),
            {"email": "missing@example.com"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "We couldn&#x27;t find an active SurveySnap account with that email address.",
        )
        self.assertEqual(len(mail.outbox), 0)

    def test_password_reset_confirm_updates_password(self):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)
        confirm_url = reverse("password_reset_confirm", kwargs={"uidb64": uid, "token": token})

        first_response = self.client.get(confirm_url)
        self.assertEqual(first_response.status_code, 302)

        response = self.client.post(
            first_response.url,
            {
                "new_password1": "NewSecurePass@456",
                "new_password2": "NewSecurePass@456",
            },
        )

        self.assertRedirects(response, reverse("password_reset_complete"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("NewSecurePass@456"))
