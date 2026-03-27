from django.contrib import admin

from .models import CanvasElement, Option, Question, Response, Survey, SurveyTemplate


class OptionInline(admin.TabularInline):
    model = Option
    extra = 0


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("question_text", "survey", "question_type", "is_required", "order")
    list_filter = ("question_type", "is_required")
    search_fields = ("question_text", "survey__title")
    inlines = [OptionInline]


@admin.register(Survey)
class SurveyAdmin(admin.ModelAdmin):
    list_display = ("title", "created_by", "survey_type", "is_published", "updated_at")
    list_filter = ("survey_type", "is_published", "visibility")
    search_fields = ("title", "description", "created_by__email")


admin.site.register(SurveyTemplate)
admin.site.register(Response)
admin.site.register(CanvasElement)
