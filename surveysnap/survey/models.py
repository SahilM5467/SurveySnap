from django.db import models
from core.models import User


# =========================
# Survey Model
# =========================
class Survey(models.Model):

    STATUS_CHOICES = (
        ("Draft", "Draft"),
        ("Active", "Active"),
        ("Closed", "Closed"),
    )

    creator = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="surveys"
    )

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)

    is_public = models.BooleanField(default=False)
    theme = models.CharField(max_length=100, blank=True, null=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="Draft"
    )

    survey_code = models.CharField(
        max_length=50,
        unique=True,
        db_index=True
    )

    allow_anonymous = models.BooleanField(default=True)
    require_email = models.BooleanField(default=False)

    response_limit = models.PositiveIntegerField(blank=True, null=True)
    expires_at = models.DateTimeField(blank=True, null=True)

    cloned_from_survey = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cloned_surveys"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


# =========================
# Survey Template Model
# =========================
class SurveyTemplate(models.Model):

    name = models.CharField(max_length=150)
    category = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)

    created_by_admin = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="admin_templates"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    is_system_template = models.BooleanField(default=False)

    creator = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="creator_templates"
    )

    source_survey = models.ForeignKey(
        Survey,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="generated_templates"
    )

    def __str__(self):
        return self.name


# =========================
# Question Model
# =========================
class Question(models.Model):

    QUESTION_TYPE_CHOICES = (
        ("MCQ", "MCQ"),
        ("Text", "Text"),
        ("Rating", "Rating"),
        ("Dropdown", "Dropdown"),
    )

    survey = models.ForeignKey(
        Survey,
        on_delete=models.CASCADE,
        related_name="questions"
    )

    question_text = models.TextField()

    question_type = models.CharField(
        max_length=20,
        choices=QUESTION_TYPE_CHOICES
    )

    is_required = models.BooleanField(default=False)

    logic_condition = models.TextField(blank=True, null=True)

    question_order = models.PositiveIntegerField(default=1)

    placeholder_text = models.CharField(
        max_length=150,
        blank=True,
        null=True
    )

    class Meta:
        ordering = ["question_order"]

    def __str__(self):
        return f"Q{self.question_order}: {self.question_text[:40]}"


# =========================
# Option Model
# =========================
class Option(models.Model):

    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name="options"
    )

    option_text = models.CharField(max_length=200)

    option_order = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["option_order"]

    def __str__(self):
        return self.option_text


# =========================
# Response Model
# =========================
class Response(models.Model):

    survey = models.ForeignKey(
        Survey,
        on_delete=models.CASCADE,
        related_name="responses"
    )

    respondent = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="responses"
    )

    submitted_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True
    )

    is_anonymous = models.BooleanField(default=False)

    respondent_email = models.EmailField(
        max_length=150,
        blank=True,
        null=True
    )

    ip_address = models.CharField(
        max_length=45,
        blank=True,
        null=True
    )

    response_pdf_path = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    def __str__(self):
        return f"Response #{self.id} - {self.survey.title}"


# =========================
# Answer Model
# =========================
class Answer(models.Model):

    response = models.ForeignKey(
        Response,
        on_delete=models.CASCADE,
        related_name="answers"
    )

    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name="answers"
    )

    # For MCQ / Dropdown
    selected_option = models.ForeignKey(
        Option,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    # For Text answers
    answer_text = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Answer #{self.id} (Response #{self.response.id})"


# =========================
# Notification Model
# =========================
class Notification(models.Model):

    NOTIFICATION_TYPE_CHOICES = (
        ("Email", "Email"),
        ("SMS", "SMS"),
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="notifications"
    )

    message = models.TextField()

    type = models.CharField(
        max_length=10,
        choices=NOTIFICATION_TYPE_CHOICES
    )

    sent_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Notification to {self.user.email}"


# =========================
# Report Model
# =========================
class Report(models.Model):

    EXPORT_FORMAT_CHOICES = (
        ("CSV", "CSV"),
        ("Excel", "Excel"),
        ("PDF", "PDF"),
    )

    survey = models.ForeignKey(
        Survey,
        on_delete=models.CASCADE,
        related_name="reports"
    )

    total_responses = models.PositiveIntegerField(default=0)

    generated_at = models.DateTimeField(auto_now_add=True)

    export_format = models.CharField(
        max_length=10,
        choices=EXPORT_FORMAT_CHOICES
    )

    response = models.ForeignKey(
        Response,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reports"
    )

    file_path = models.CharField(max_length=255)

    def __str__(self):
        return f"Report - {self.survey.title} ({self.export_format})"