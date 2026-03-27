import uuid

from django.conf import settings
from django.db import models


class SurveyTemplate(models.Model):
    TEMPLATE_TYPE_CHOICES = [
        ("regular", "Regular"),
        ("custom", "Custom"),
    ]

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    template_type = models.CharField(
        max_length=20,
        choices=TEMPLATE_TYPE_CHOICES,
        default="regular",
    )
    category = models.CharField(max_length=100, blank=True)
    thumbnail = models.ImageField(
        upload_to="template_thumbnails/",
        null=True,
        blank=True,
    )
    structure = models.JSONField(default=dict, blank=True)
    theme = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_survey_templates",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class Survey(models.Model):
    SURVEY_TYPE_CHOICES = [
        ("regular", "Regular"),
        ("custom", "Custom"),
    ]

    VISIBILITY_CHOICES = [
        ("public", "Public"),
        ("private", "Private"),
    ]

    title = models.CharField(max_length=255, default="Untitled Survey")
    description = models.TextField(blank=True)
    category = models.CharField(max_length=100, blank=True)
    survey_type = models.CharField(
        max_length=20,
        choices=SURVEY_TYPE_CHOICES,
        default="regular",
    )
    template = models.ForeignKey(
        SurveyTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="surveys",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="created_surveys",
    )
    logo = models.ImageField(upload_to="survey_logos/", null=True, blank=True)
    theme = models.JSONField(default=dict, blank=True)
    settings = models.JSONField(default=dict, blank=True)
    structure = models.JSONField(default=dict, blank=True)
    is_published = models.BooleanField(default=False)
    visibility = models.CharField(
        max_length=10,
        choices=VISIBILITY_CHOICES,
        default="private",
    )
    expiry_date = models.DateTimeField(null=True, blank=True)
    share_token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    share_url = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["created_by", "updated_at"]),
            models.Index(fields=["is_published"]),
            models.Index(fields=["share_token"]),
        ]

    def __str__(self):
        return self.title


class Question(models.Model):
    QUESTION_TYPE_CHOICES = [
        ("short_answer", "Short Answer"),
        ("paragraph", "Paragraph"),
        ("multiple_choice", "Multiple Choice"),
        ("checkboxes", "Checkboxes"),
        ("dropdown", "Dropdown"),
        ("date", "Date"),
        ("rating", "Rating"),
        ("file_upload", "File Upload"),
    ]

    survey = models.ForeignKey(
        Survey,
        on_delete=models.CASCADE,
        related_name="questions",
    )
    question_text = models.TextField()
    question_type = models.CharField(max_length=30, choices=QUESTION_TYPE_CHOICES)
    is_required = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)
    settings = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "id"]
        indexes = [
            models.Index(fields=["survey", "order"]),
        ]

    def __str__(self):
        return self.question_text[:60]


class Option(models.Model):
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name="options",
    )
    option_text = models.CharField(max_length=255)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]
        indexes = [
            models.Index(fields=["question", "order"]),
        ]

    def __str__(self):
        return self.option_text


class Response(models.Model):
    survey = models.ForeignKey(
        Survey,
        on_delete=models.CASCADE,
        related_name="responses",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    answers = models.JSONField()
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-submitted_at"]

    def __str__(self):
        return f"Response {self.pk} - {self.survey.title}"


class CanvasElement(models.Model):
    ELEMENT_TYPE_CHOICES = [
        ("question", "Question"),
        ("text", "Text"),
        ("image", "Image"),
        ("divider", "Divider"),
    ]

    survey = models.ForeignKey(
        Survey,
        on_delete=models.CASCADE,
        related_name="canvas_elements",
    )
    question = models.ForeignKey(
        Question,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="canvas_elements",
    )
    element_type = models.CharField(max_length=20, choices=ELEMENT_TYPE_CHOICES)
    x = models.FloatField(default=24)
    y = models.FloatField(default=24)
    width = models.FloatField(default=320)
    height = models.FloatField(default=140)
    z_index = models.IntegerField(default=0)
    order = models.PositiveIntegerField(default=0)
    content = models.JSONField(default=dict, blank=True)
    style = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "id"]
        indexes = [
            models.Index(fields=["survey", "order"]),
            models.Index(fields=["survey", "z_index"]),
        ]

    def __str__(self):
        return f"{self.element_type} - {self.survey.title}"
