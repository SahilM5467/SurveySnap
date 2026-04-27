from django.test import TestCase
from django.urls import reverse

from core.models import User
from survey.models import Question, Response, Survey, SurveyTemplate


class SurveyTemplateLibraryTests(TestCase):
    def setUp(self):
        self.creator = User.objects.create_user(
            email="creator@example.com",
            password="CreatorPass@123",
            first_name="Creator",
            last_name="User",
            role="creator",
        )
        self.client.force_login(self.creator)

    def test_create_survey_page_shows_built_in_templates(self):
        response = self.client.get(reverse("create_survey_page"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Customer Satisfaction Survey")
        self.assertContains(response, "Customer Support Feedback Survey")

    def test_builder_bootstrap_prefills_selected_template(self):
        response = self.client.get(
            reverse("survey_builder"),
            {"template": "product-feedback-survey"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Product Feedback Survey")
        self.assertContains(response, "Which features do you use the most?")

    def test_template_preview_route_renders_template_questions(self):
        response = self.client.get(
            reverse("template_preview", kwargs={"template_slug": "event-feedback-survey"})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Event Feedback Survey")
        self.assertContains(response, "How would you rate the event overall?")


class CreatorSurveyDeleteTests(TestCase):
    def setUp(self):
        self.creator = User.objects.create_user(
            email="owner@example.com",
            password="CreatorPass@123",
            first_name="Owner",
            last_name="User",
            role="creator",
        )
        self.other_creator = User.objects.create_user(
            email="other@example.com",
            password="CreatorPass@123",
            first_name="Other",
            last_name="User",
            role="creator",
        )

    def test_creator_can_delete_own_survey(self):
        survey = Survey.objects.create(
            title="Delete Me",
            created_by=self.creator,
            survey_type="regular",
            visibility="public",
        )
        self.client.force_login(self.creator)

        response = self.client.post(reverse("delete_creator_survey", kwargs={"survey_id": survey.id}))

        self.assertRedirects(response, reverse("my_surveys"))
        self.assertFalse(Survey.objects.filter(id=survey.id).exists())

    def test_creator_cannot_delete_another_creators_survey(self):
        survey = Survey.objects.create(
            title="Protected Survey",
            created_by=self.other_creator,
            survey_type="regular",
            visibility="public",
        )
        self.client.force_login(self.creator)

        response = self.client.post(reverse("delete_creator_survey", kwargs={"survey_id": survey.id}))

        self.assertEqual(response.status_code, 404)
        self.assertTrue(Survey.objects.filter(id=survey.id).exists())


class AnalyticsAllSurveysTests(TestCase):
    def setUp(self):
        self.creator = User.objects.create_user(
            email="analytics@example.com",
            password="CreatorPass@123",
            first_name="Analytics",
            last_name="User",
            role="creator",
        )
        self.client.force_login(self.creator)

    def test_analytics_can_show_combined_published_and_draft_survey_data(self):
        published_survey = Survey.objects.create(
            title="Published Survey",
            created_by=self.creator,
            survey_type="regular",
            visibility="public",
            is_published=True,
        )
        draft_survey = Survey.objects.create(
            title="Draft Survey",
            created_by=self.creator,
            survey_type="regular",
            visibility="private",
            is_published=False,
        )

        published_question = Question.objects.create(
            survey=published_survey,
            question_text="How was the published survey?",
            question_type="short_answer",
            order=1,
        )
        draft_question = Question.objects.create(
            survey=draft_survey,
            question_text="How was the draft survey?",
            question_type="short_answer",
            order=1,
        )

        Response.objects.create(
            survey=published_survey,
            answers={
                "answers": [
                    {
                        "question_id": published_question.id,
                        "question_text": published_question.question_text,
                        "question_type": published_question.question_type,
                        "value": "Great",
                    }
                ]
            },
        )
        Response.objects.create(
            survey=draft_survey,
            answers={
                "answers": [
                    {
                        "question_id": draft_question.id,
                        "question_text": draft_question.question_text,
                        "question_type": draft_question.question_type,
                        "value": "Promising",
                    }
                ]
            },
        )

        response = self.client.get(reverse("analytics"), {"survey": "all"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "All Surveys Overview")
        self.assertContains(response, "Published + Draft")
        self.assertContains(response, "2 responses")


class AdminTemplateManagementTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="admin@example.com",
            password="AdminPass@123",
            first_name="Admin",
            last_name="User",
            role="admin",
        )
        self.creator = User.objects.create_user(
            email="creator2@example.com",
            password="CreatorPass@123",
            first_name="Template",
            last_name="Owner",
            role="creator",
        )
        self.client.force_login(self.admin)

    def test_seed_library_adds_six_templates_to_database(self):
        response = self.client.post(reverse("manage_templates"), {"action": "seed_library"})

        self.assertRedirects(response, reverse("manage_templates"))
        self.assertEqual(SurveyTemplate.objects.count(), 6)
        self.assertTrue(SurveyTemplate.objects.filter(title="Customer Satisfaction Survey").exists())

    def test_admin_can_create_update_and_delete_template(self):
        create_response = self.client.post(
            reverse("manage_templates"),
            {
                "action": "create",
                "title": "Admin Template",
                "description": "Template managed by admin.",
                "category": "Operations",
                "template_type": "regular",
                "created_by": str(self.creator.id),
                "is_active": "on",
            },
        )

        self.assertRedirects(create_response, reverse("manage_templates"))
        template = SurveyTemplate.objects.get(title="Admin Template")
        self.assertEqual(template.created_by, self.creator)

        update_response = self.client.post(
            reverse("manage_templates"),
            {
                "action": "update",
                "template_id": str(template.id),
                "title": "Updated Admin Template",
                "description": "Updated description.",
                "category": "Research",
                "template_type": "custom",
                "created_by": "system",
            },
        )

        self.assertRedirects(update_response, reverse("manage_templates"))
        template.refresh_from_db()
        self.assertEqual(template.title, "Updated Admin Template")
        self.assertEqual(template.template_type, "custom")
        self.assertIsNone(template.created_by)

        delete_response = self.client.post(
            reverse("manage_templates"),
            {
                "action": "delete",
                "template_id": str(template.id),
            },
        )

        self.assertRedirects(delete_response, reverse("manage_templates"))
        self.assertFalse(SurveyTemplate.objects.filter(id=template.id).exists())
