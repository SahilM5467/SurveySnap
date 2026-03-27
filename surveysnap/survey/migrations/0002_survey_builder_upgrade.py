import uuid

import django.db.models.deletion
from django.db import migrations, models


def populate_share_tokens(apps, schema_editor):
    Survey = apps.get_model("survey", "Survey")
    seen_tokens = set()
    for survey in Survey.objects.order_by("pk"):
        token = survey.share_token
        if token is None or token in seen_tokens:
            survey.share_token = uuid.uuid4()
            survey.save(update_fields=["share_token"])
            token = survey.share_token
        seen_tokens.add(token)


class Migration(migrations.Migration):

    dependencies = [
        ("survey", "0001_initial"),
    ]

    operations = [
        migrations.RenameModel(
            old_name="Choice",
            new_name="Option",
        ),
        migrations.RenameField(
            model_name="option",
            old_name="choice_text",
            new_name="option_text",
        ),
        migrations.RemoveField(
            model_name="option",
            name="vote_count",
        ),
        migrations.AddField(
            model_name="option",
            name="order",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AlterField(
            model_name="option",
            name="question",
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="options", to="survey.question"),
        ),
        migrations.AlterModelOptions(
            name="option",
            options={"ordering": ["order", "id"]},
        ),
        migrations.AddIndex(
            model_name="option",
            index=models.Index(fields=["question", "order"], name="survey_opti_questio_4f7a5d_idx"),
        ),
        migrations.RemoveField(
            model_name="question",
            name="image",
        ),
        migrations.RemoveField(
            model_name="question",
            name="section",
        ),
        migrations.AddField(
            model_name="question",
            name="settings",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="question",
            name="updated_at",
            field=models.DateTimeField(auto_now=True, null=True),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name="question",
            name="question_type",
            field=models.CharField(choices=[("short_answer", "Short Answer"), ("paragraph", "Paragraph"), ("multiple_choice", "Multiple Choice"), ("checkboxes", "Checkboxes"), ("dropdown", "Dropdown"), ("date", "Date"), ("rating", "Rating"), ("file_upload", "File Upload")], max_length=30),
        ),
        migrations.AlterModelOptions(
            name="question",
            options={"ordering": ["order", "id"]},
        ),
        migrations.AddIndex(
            model_name="question",
            index=models.Index(fields=["survey", "order"], name="survey_ques_survey__d17cb8_idx"),
        ),
        migrations.AddField(
            model_name="survey",
            name="settings",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="survey",
            name="share_token",
            field=models.UUIDField(editable=False, null=True),
        ),
        migrations.AddField(
            model_name="survey",
            name="structure",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AlterField(
            model_name="survey",
            name="survey_type",
            field=models.CharField(choices=[("regular", "Regular"), ("custom", "Custom")], default="regular", max_length=20),
        ),
        migrations.AddIndex(
            model_name="survey",
            index=models.Index(fields=["created_by", "updated_at"], name="survey_surv_created_8d63f2_idx"),
        ),
        migrations.AddIndex(
            model_name="survey",
            index=models.Index(fields=["is_published"], name="survey_surv_is_publ_3cf3e4_idx"),
        ),
        migrations.AddIndex(
            model_name="survey",
            index=models.Index(fields=["share_token"], name="survey_surv_share_t_2802cf_idx"),
        ),
        migrations.AddField(
            model_name="canvaselement",
            name="order",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="canvaselement",
            name="question",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="canvas_elements", to="survey.question"),
        ),
        migrations.AddField(
            model_name="canvaselement",
            name="updated_at",
            field=models.DateTimeField(auto_now=True, null=True),
            preserve_default=False,
        ),
        migrations.RemoveField(
            model_name="canvaselement",
            name="rotation",
        ),
        migrations.AlterModelOptions(
            name="canvaselement",
            options={"ordering": ["order", "id"]},
        ),
        migrations.AddIndex(
            model_name="canvaselement",
            index=models.Index(fields=["survey", "order"], name="survey_canv_survey__5cf981_idx"),
        ),
        migrations.AddIndex(
            model_name="canvaselement",
            index=models.Index(fields=["survey", "z_index"], name="survey_canv_survey__c1fd96_idx"),
        ),
        migrations.AlterField(
            model_name="surveytemplate",
            name="template_type",
            field=models.CharField(choices=[("regular", "Regular"), ("custom", "Custom")], default="regular", max_length=20),
        ),
        migrations.RunPython(populate_share_tokens, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="survey",
            name="share_token",
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
    ]
