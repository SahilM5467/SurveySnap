import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from io import BytesIO
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.hashers import check_password, make_password
from django.db import transaction
from django.db.models import Count, Prefetch
from django.db.models.functions import TruncMonth
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_GET, require_POST

from core.forms import RespondentProfileForm
from core.models import User

from .decorators import role_required
from .models import CanvasElement, Option, Question, Response, Survey, SurveyTemplate

try:
    import qrcode
    import qrcode.image.svg
except ImportError:  # pragma: no cover - optional dependency
    qrcode = None


QUESTION_TYPES_REQUIRING_OPTIONS = {"multiple_choice", "checkboxes", "dropdown"}
DEFAULT_THEME = {
    "appearance": "light",
    "accent_color": "#2563eb",
    "surface_color": "#ffffff",
    "font_family": "Poppins, sans-serif",
}
DEFAULT_SETTINGS = {
    "collect_email": False,
    "is_anonymous": True,
    "description": "",
    "private_password_configured": False,
}


def _json_error(message, status=400):
    return JsonResponse({"status": "error", "message": message}, status=status)


def _parse_json_body(request):
    try:
        return json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return None


def _normalize_question_type(question_type):
    aliases = {
        "short": "short_answer",
        "long": "paragraph",
        "single": "multiple_choice",
        "multiple": "checkboxes",
        "canvas": "custom",
    }
    return aliases.get(question_type, question_type)


def _normalize_mode(mode):
    mode = _normalize_question_type(mode or "regular")
    return mode if mode in {"regular", "custom"} else "regular"


def _normalize_visibility(visibility):
    return visibility if visibility in {"public", "private"} else "public"


def _get_private_access_session_key(survey):
    return f"survey_private_access_{survey.pk}"


def _survey_password_hash(survey):
    return (survey.settings or {}).get("access_password_hash", "")


def _client_settings(settings):
    merged = DEFAULT_SETTINGS | (settings or {})
    merged.pop("access_password_hash", None)
    merged["access_password"] = ""
    merged["private_password_configured"] = bool((settings or {}).get("access_password_hash"))
    return merged


def _has_private_access(request, survey):
    if not request.user.is_authenticated:
        return False
    password_hash = _survey_password_hash(survey)
    if not password_hash:
        return False
    return request.session.get(_get_private_access_session_key(survey)) == password_hash


def _set_private_access(request, survey):
    request.session[_get_private_access_session_key(survey)] = _survey_password_hash(survey)


def _clear_private_access(request, survey):
    request.session.pop(_get_private_access_session_key(survey), None)


def _validate_payload(payload, for_publish=False):
    title = (payload.get("title") or "").strip() or "Untitled Survey"
    questions = payload.get("questions") or []

    if for_publish and not questions:
        raise ValueError(_("Add at least one question before publishing."))

    normalized_questions = []
    for index, question in enumerate(questions):
        question_text = (question.get("question_text") or "").strip()
        question_type = _normalize_question_type(question.get("question_type"))
        options = [
            {"option_text": (option.get("option_text") or "").strip()}
            for option in (question.get("options") or [])
            if (option.get("option_text") or "").strip()
        ]

        if for_publish and not question_text:
            raise ValueError(_(f"Question {index + 1} needs text before publishing."))

        if question_type not in {
            "short_answer",
            "paragraph",
            "multiple_choice",
            "checkboxes",
            "dropdown",
            "date",
            "rating",
            "file_upload",
        }:
            raise ValueError(_(f"Question {index + 1} has an unsupported question type."))

        if question_type in QUESTION_TYPES_REQUIRING_OPTIONS and for_publish and len(options) < 2:
            raise ValueError(_(f"Question {index + 1} needs at least two options."))

        normalized_questions.append(
            {
                "question_text": question_text or _("Untitled question"),
                "question_type": question_type,
                "is_required": bool(question.get("is_required")),
                "settings": question.get("settings") or {},
                "options": options,
            }
        )

    canvas_elements = []
    for index, element in enumerate(payload.get("canvas_elements") or []):
        canvas_elements.append(
            {
                "client_id": element.get("client_id"),
                "question_client_id": element.get("question_client_id"),
                "element_type": element.get("element_type") or "question",
                "x": float(element.get("x", 24)),
                "y": float(element.get("y", 24)),
                "width": float(element.get("width", 320)),
                "height": float(element.get("height", 140)),
                "z_index": int(element.get("z_index", index)),
                "content": element.get("content") or {},
                "style": element.get("style") or {},
            }
        )

    theme = DEFAULT_THEME | (payload.get("theme") or {})
    settings = DEFAULT_SETTINGS | (payload.get("settings") or {})
    settings["description"] = payload.get("description", settings.get("description", ""))
    visibility = _normalize_visibility(payload.get("visibility"))
    access_password = (settings.get("access_password") or "").strip()

    if for_publish and visibility == "private" and not access_password and not settings.get("private_password_configured"):
        raise ValueError(_("Add a password before publishing a private survey."))

    return {
        "title": title,
        "description": payload.get("description", ""),
        "mode": _normalize_mode(payload.get("mode")),
        "visibility": visibility,
        "questions": normalized_questions,
        "canvas_elements": canvas_elements,
        "theme": theme,
        "settings": settings,
    }


def _build_share_url(request, survey):
    return request.build_absolute_uri(
        reverse("public_survey_detail", kwargs={"share_token": survey.share_token})
    )


def _build_qr_svg(url):
    if qrcode is None:
        return ""

    image = qrcode.make(url, image_factory=qrcode.image.svg.SvgImage)
    buffer = BytesIO()
    image.save(buffer)
    return buffer.getvalue().decode("utf-8")


def _serialize_question(question):
    return {
        "id": question.id,
        "client_id": f"question-{question.id}",
        "question_text": question.question_text,
        "question_type": question.question_type,
        "is_required": question.is_required,
        "settings": question.settings or {},
        "options": [
            {
                "id": option.id,
                "option_text": option.option_text,
                "order": option.order,
            }
            for option in question.options.all()
        ],
    }


def _serialize_canvas_element(element):
    question_client_id = f"question-{element.question_id}" if element.question_id else None
    return {
        "id": element.id,
        "client_id": element.content.get("client_id") or f"canvas-{element.id}",
        "question_client_id": question_client_id,
        "element_type": element.element_type,
        "x": element.x,
        "y": element.y,
        "width": element.width,
        "height": element.height,
        "z_index": element.z_index,
        "content": element.content or {},
        "style": element.style or {},
    }


def _serialize_survey(request, survey):
    questions = [
        _serialize_question(question)
        for question in survey.questions.all()
    ]
    canvas_elements = [
        _serialize_canvas_element(element)
        for element in survey.canvas_elements.all()
    ]
    share_url = survey.share_url or _build_share_url(request, survey)
    return {
        "survey_id": survey.id,
        "title": survey.title,
        "description": survey.description,
        "mode": survey.survey_type,
        "visibility": survey.visibility,
        "theme": DEFAULT_THEME | (survey.theme or {}),
        "settings": _client_settings(survey.settings),
        "questions": questions,
        "canvas_elements": canvas_elements,
        "is_published": survey.is_published,
        "share_url": share_url,
        "preview_url": reverse("survey_preview", kwargs={"survey_id": survey.id}),
        "publish_url": reverse("publish_survey", kwargs={"survey_id": survey.id}),
        "unpublish_url": reverse("unpublish_survey", kwargs={"survey_id": survey.id}),
        "save_url": reverse("save_survey", kwargs={"survey_id": survey.id}),
        "qr_svg": _build_qr_svg(share_url),
    }


def _build_preview_answer(question, index=0):
    options = list(question.options.all())
    option_labels = [option.option_text for option in options]
    primary_option = option_labels[0] if option_labels else "Option 1"
    secondary_option = option_labels[1] if len(option_labels) > 1 else primary_option

    sample_answers = {
        "short_answer": {
            "input_value": f"Sample answer {index + 1}",
            "placeholder": "Type a short answer",
            "helper_text": "Preview uses a sample text response only.",
        },
        "paragraph": {
            "input_value": (
                "This is a sample long answer to help you review spacing, "
                "readability, and response layout in preview mode."
            ),
            "placeholder": "Type a longer answer",
            "helper_text": "Preview text is for testing only and will not be saved.",
        },
        "multiple_choice": {
            "selected_option": primary_option,
            "helper_text": "One option is pre-selected for testing the layout.",
        },
        "checkboxes": {
            "selected_options": [label for label in [primary_option, secondary_option] if label],
            "helper_text": "Sample selections are shown only in preview mode.",
        },
        "dropdown": {
            "selected_option": primary_option,
            "helper_text": "A sample dropdown value is shown for testing.",
        },
        "date": {
            "input_value": "2026-03-28",
            "helper_text": "Date shown here is a preview example and is not submitted.",
        },
        "rating": {
            "rating_value": 4,
            "helper_text": "A four-star sample rating helps you preview the scale.",
        },
        "file_upload": {
            "file_name": "sample-document.pdf",
            "helper_text": "File names are visual placeholders only in preview mode.",
        },
    }

    return sample_answers.get(
        question.question_type,
        {
            "input_value": f"Sample answer {index + 1}",
            "placeholder": "Type a short answer",
            "helper_text": "Preview uses a sample text response only.",
        },
    )


def _build_preview_context(survey, preview_mode):
    questions = list(survey.questions.all())
    question_cards = []
    question_preview_map = {}

    for index, question in enumerate(questions):
        preview_answer = _build_preview_answer(question, index) if preview_mode else {}
        card = {
            "question": question,
            "question_number": index + 1,
            "preview_answer": preview_answer,
        }
        question_cards.append(card)
        question_preview_map[question.id] = card

    canvas_elements = []
    for element in survey.canvas_elements.all():
        question_card = question_preview_map.get(element.question_id)
        canvas_elements.append(
            {
                "element": element,
                "question_card": question_card,
            }
        )

    return {
        "preview_questions": question_cards,
        "preview_canvas_elements": canvas_elements,
    }


def _get_response_input_name(question):
    return f"question_{question.id}"


def _serialize_uploaded_file(uploaded_file):
    return {
        "name": uploaded_file.name,
        "size": uploaded_file.size,
        "content_type": getattr(uploaded_file, "content_type", "") or "",
    }


def _collect_response_answers(request, survey):
    answers = []
    errors = []

    for index, question in enumerate(survey.questions.all(), start=1):
        input_name = _get_response_input_name(question)
        raw_value = None
        is_answered = False

        if question.question_type == "checkboxes":
            raw_value = [value.strip() for value in request.POST.getlist(input_name) if value.strip()]
            is_answered = bool(raw_value)
        elif question.question_type == "file_upload":
            uploaded_file = request.FILES.get(input_name)
            if uploaded_file:
                raw_value = _serialize_uploaded_file(uploaded_file)
                is_answered = True
        else:
            raw_value = (request.POST.get(input_name) or "").strip()
            is_answered = bool(raw_value)

        if question.is_required and not is_answered:
            errors.append(_(f"Question {index} is required."))
            continue

        if not is_answered:
            normalized_value = [] if question.question_type == "checkboxes" else ""
        elif question.question_type in {"multiple_choice", "dropdown"}:
            valid_options = set(question.options.values_list("option_text", flat=True))
            if raw_value not in valid_options:
                errors.append(_(f"Question {index} contains an invalid option."))
                continue
            normalized_value = raw_value
        elif question.question_type == "checkboxes":
            valid_options = set(question.options.values_list("option_text", flat=True))
            invalid_values = [value for value in raw_value if value not in valid_options]
            if invalid_values:
                errors.append(_(f"Question {index} contains an invalid selection."))
                continue
            normalized_value = raw_value
        elif question.question_type == "rating":
            try:
                normalized_value = int(raw_value)
            except (TypeError, ValueError):
                errors.append(_(f"Question {index} needs a valid rating."))
                continue

            rating_max = int((question.settings or {}).get("rating_max") or 5)
            if normalized_value < 1 or normalized_value > rating_max:
                errors.append(_(f"Question {index} rating must be between 1 and {rating_max}."))
                continue
        elif question.question_type == "file_upload":
            normalized_value = raw_value or {}
        else:
            normalized_value = raw_value

        answers.append(
            {
                "question_id": question.id,
                "question_text": question.question_text,
                "question_type": question.question_type,
                "value": normalized_value,
            }
        )

    return answers, errors


def _format_answer_value(value):
    if isinstance(value, list):
        return ", ".join(str(item) for item in value) if value else "No response"
    if isinstance(value, dict):
        return value.get("name") or "File attached"
    return value or "No response"


def _get_user_display_name(user):
    full_name = " ".join(
        part.strip()
        for part in [getattr(user, "first_name", "") or "", getattr(user, "last_name", "") or ""]
        if part and part.strip()
    ).strip()
    return full_name or getattr(user, "email", "") or f"User {user.pk}"


def _response_answer_items(response):
    if not isinstance(response.answers, dict):
        return []

    answer_items = response.answers.get("answers", [])
    if isinstance(answer_items, list) and answer_items:
        normalized_items = []
        for answer in answer_items:
            if not isinstance(answer, dict):
                continue
            question_id = answer.get("question_id")
            if isinstance(question_id, str) and question_id.isdigit():
                question_id = int(question_id)
            normalized_items.append(
                {
                    "question_id": question_id,
                    "question_text": answer.get("question_text", ""),
                    "question_type": answer.get("question_type", ""),
                    "value": answer.get("value"),
                }
            )
        return normalized_items

    survey_questions = list(response.survey.questions.all())
    if not survey_questions:
        return []

    questions_by_id = {str(question.id): question for question in survey_questions}
    questions_by_text = {question.question_text.strip().lower(): question for question in survey_questions}
    legacy_items = []

    for key, raw_value in response.answers.items():
        if key in {"answers", "submitted_via", "respondent"}:
            continue

        question = questions_by_id.get(str(key))
        if question is None and isinstance(raw_value, dict):
            raw_question_id = raw_value.get("question_id")
            raw_question_text = (raw_value.get("question_text") or "").strip().lower()
            if raw_question_id is not None:
                question = questions_by_id.get(str(raw_question_id))
            if question is None and raw_question_text:
                question = questions_by_text.get(raw_question_text)
        if question is None:
            question = questions_by_text.get(str(key).strip().lower())
        if question is None:
            continue

        normalized_value = raw_value.get("value") if isinstance(raw_value, dict) and "value" in raw_value else raw_value
        legacy_items.append(
            {
                "question_id": question.id,
                "question_text": question.question_text,
                "question_type": question.question_type,
                "value": normalized_value,
            }
        )

    return legacy_items


def _response_answer_lookup(response):
    answer_lookup = {}
    for answer in _response_answer_items(response):
        question_id = answer.get("question_id")
        if question_id is not None:
            answer_lookup[question_id] = answer
    return answer_lookup


def _format_export_datetime(value):
    if not value:
        return "-"
    if isinstance(value, datetime):
        return timezone.localtime(value).strftime("%Y-%m-%d %I:%M %p")
    return str(value)


@transaction.atomic
def _persist_survey_payload(request, survey, payload, publish=False, force_publish_state=None):
    validated = _validate_payload(payload, for_publish=publish)
    share_url = _build_share_url(request, survey)
    existing_settings = survey.settings or {}
    raw_password = (validated["settings"].get("access_password") or "").strip()
    password_hash = existing_settings.get("access_password_hash", "")

    if validated["visibility"] == "private":
        if raw_password:
            password_hash = make_password(raw_password)
        elif publish and not password_hash:
            raise ValueError(_("Add a password before publishing a private survey."))
    else:
        password_hash = ""

    survey_settings = {
        **validated["settings"],
        "private_password_configured": bool(password_hash),
    }
    survey_settings.pop("access_password", None)
    if password_hash:
        survey_settings["access_password_hash"] = password_hash
    else:
        survey_settings.pop("access_password_hash", None)

    survey.title = validated["title"]
    survey.description = validated["description"]
    survey.survey_type = validated["mode"]
    survey.visibility = validated["visibility"]
    survey.theme = validated["theme"]
    survey.settings = survey_settings
    survey.share_url = share_url
    survey.is_published = (
        publish or survey.is_published
        if force_publish_state is None
        else force_publish_state
    )
    survey.structure = {
        "mode": validated["mode"],
        "questions": validated["questions"],
        "canvas_elements": validated["canvas_elements"],
        "theme": validated["theme"],
        "visibility": validated["visibility"],
        "settings": survey_settings,
    }
    survey.save(
        update_fields=[
            "title",
            "description",
            "survey_type",
            "visibility",
            "theme",
            "settings",
            "structure",
            "share_url",
            "is_published",
            "updated_at",
        ]
    )

    survey.questions.all().delete()
    survey.canvas_elements.all().delete()

    questions_to_create = []
    for order, question in enumerate(validated["questions"], start=1):
        questions_to_create.append(
            Question(
                survey=survey,
                question_text=question["question_text"],
                question_type=question["question_type"],
                is_required=question["is_required"],
                order=order,
                settings=question["settings"],
            )
        )
    created_questions = Question.objects.bulk_create(questions_to_create)

    option_objects = []
    question_by_client_id = {}
    for order, (created_question, question_payload) in enumerate(
        zip(created_questions, payload.get("questions") or []),
        start=1,
    ):
        client_id = question_payload.get("client_id") or f"question-{order}"
        question_by_client_id[client_id] = created_question
        for option_order, option in enumerate(question_payload.get("options") or [], start=1):
            option_text = (option.get("option_text") or "").strip()
            if option_text:
                option_objects.append(
                    Option(
                        question=created_question,
                        option_text=option_text,
                        order=option_order,
                    )
                )
    if option_objects:
        Option.objects.bulk_create(option_objects)

    canvas_objects = []
    for order, element in enumerate(validated["canvas_elements"], start=1):
        linked_question = None
        if element["question_client_id"]:
            linked_question = question_by_client_id.get(element["question_client_id"])
        canvas_objects.append(
            CanvasElement(
                survey=survey,
                question=linked_question,
                element_type=element["element_type"],
                x=element["x"],
                y=element["y"],
                width=element["width"],
                height=element["height"],
                z_index=element["z_index"],
                order=order,
                content=element["content"] | {"client_id": element["client_id"]},
                style=element["style"],
            )
        )
    if canvas_objects:
        CanvasElement.objects.bulk_create(canvas_objects)

    survey = (
        Survey.objects.filter(pk=survey.pk)
        .prefetch_related(
            Prefetch("questions", queryset=Question.objects.prefetch_related("options")),
            "canvas_elements",
        )
        .get()
    )
    return _serialize_survey(request, survey)


def _survey_queryset():
    return Survey.objects.select_related("created_by").prefetch_related(
        Prefetch("questions", queryset=Question.objects.prefetch_related("options")),
        "canvas_elements",
    )


# ========================================================================================================
# Admin
# ========================================================================================================

@role_required(allowed_roles=["admin"])
def AdminDashboardView(request):
    creators = User.objects.filter(role="creator").count()
    respondents = User.objects.filter(role="respondent").count()
    admins = User.objects.filter(role="admin").count()

    surveys = Survey.objects.count()
    draft_surveys = Survey.objects.filter(is_published=False).count()
    active_surveys = Survey.objects.filter(is_published=True).count()
    closed_surveys = Survey.objects.filter(expiry_date__isnull=False).count()

    templates = SurveyTemplate.objects.count()
    system_templates = SurveyTemplate.objects.filter(created_by__isnull=True).count()
    creator_templates = SurveyTemplate.objects.filter(created_by__isnull=False).count()

    template_categories = (
        SurveyTemplate.objects.values("category")
        .annotate(total=Count("id"))
        .order_by("-total")
    )

    monthly_surveys = (
        Survey.objects.annotate(month=TruncMonth("created_at"))
        .values("month")
        .annotate(total=Count("id"))
        .order_by("month")
    )

    top_creators = (
        Survey.objects.values("created_by__first_name", "created_by__last_name")
        .annotate(total=Count("id"))
        .order_by("-total")[:5]
    )

    top_template_creators = (
        SurveyTemplate.objects.values("created_by__first_name", "created_by__last_name")
        .annotate(total=Count("id"))
        .order_by("-total")[:5]
    )

    context = {
        "creators": creators,
        "respondents": respondents,
        "admins": admins,
        "surveys": surveys,
        "draft_surveys": draft_surveys,
        "active_surveys": active_surveys,
        "closed_surveys": closed_surveys,
        "templates": templates,
        "system_templates": system_templates,
        "creator_templates": creator_templates,
        "categories": [item["category"] or "Uncategorized" for item in template_categories],
        "category_counts": [item["total"] for item in template_categories],
        "months": [item["month"].strftime("%b") for item in monthly_surveys if item["month"]],
        "survey_counts": [item["total"] for item in monthly_surveys if item["month"]],
        "top_creators": top_creators,
        "top_template_creators": top_template_creators,
        "recent_surveys": Survey.objects.select_related("created_by").order_by("-created_at")[:5],
        "recent_templates": SurveyTemplate.objects.order_by("-created_at")[:5],
    }
    return render(request, "survey/admin/admin_dashboard.html", context)


@role_required(allowed_roles=["admin"])
def MangeUsersView(request):
    search = request.GET.get("search")
    users = User.objects.filter(email__icontains=search) if search else User.objects.all().order_by("-id")
    return render(request, "survey/admin/manage_users.html", {"users": users})


@role_required(allowed_roles=["admin"])
def add_user(request):
    if request.method == "POST":
        User.objects.create_user(
            email=request.POST.get("email"),
            password=request.POST.get("password"),
            first_name=request.POST.get("first_name"),
            last_name=request.POST.get("last_name"),
            gender=request.POST.get("gender"),
            phone_no=request.POST.get("phone_no"),
            role=request.POST.get("role"),
        )
        messages.success(request, "User added successfully")
        return redirect("manage_users")

    return render(request, "survey/admin/add_user.html")


@role_required(allowed_roles=["admin"])
def edit_user(request, id):
    user = get_object_or_404(User, id=id)

    if request.method == "POST":
        user.email = request.POST.get("email")
        user.first_name = request.POST.get("first_name")
        user.last_name = request.POST.get("last_name")
        user.gender = request.POST.get("gender")
        user.phone_no = request.POST.get("phone_no")
        user.role = request.POST.get("role")

        if request.POST.get("password"):
            user.set_password(request.POST.get("password"))

        user.save()
        messages.success(request, "User updated successfully")
        return redirect("manage_users")

    return render(request, "survey/admin/edit_user.html", {"user": user})


@role_required(allowed_roles=["admin"])
def delete_user(request, id):
    get_object_or_404(User, id=id).delete()
    messages.success(request, "User deleted successfully")
    return redirect("manage_users")


@role_required(allowed_roles=["admin"])
def MangeSurveysView(request):
    return render(request, "survey/admin/manage_surveys.html")


@role_required(allowed_roles=["admin"])
def ManageTemplatesView(request):
    return render(request, "survey/admin/manage_templates.html")


@role_required(allowed_roles=["admin"])
def ReportsView(request):
    return render(request, "survey/admin/reports.html")


# ========================================================================================================
# Survey Creator
# ========================================================================================================

@role_required(allowed_roles=["creator"])
def CreatorDashboardView(request):
    surveys = list(
        Survey.objects.filter(created_by=request.user)
        .annotate(
            question_count=Count("questions", distinct=True),
            response_count=Count("responses", distinct=True),
        )
        .order_by("-updated_at")
    )
    recent_surveys = surveys[:4]
    live_surveys = [survey for survey in surveys if survey.is_published][:4]
    draft_surveys = [survey for survey in surveys if not survey.is_published][:4]
    total_responses = sum(survey.response_count for survey in surveys)
    published_count = sum(1 for survey in surveys if survey.is_published)
    draft_count = len(surveys) - published_count
    private_count = sum(1 for survey in surveys if survey.visibility == "private")
    average_responses = round(total_responses / len(surveys), 1) if surveys else 0

    recent_responses = []
    response_queryset = (
        Response.objects.filter(survey__created_by=request.user)
        .select_related("survey", "user")
        .order_by("-submitted_at")[:6]
    )
    for response in response_queryset:
        recent_responses.append(
            {
                "survey_title": response.survey.title,
                "respondent_name": _get_user_display_name(response.user) if response.user else "Anonymous respondent",
                "submitted_at": response.submitted_at,
                "answer_count": len(_response_answer_items(response)),
            }
        )

    context = {
        "survey_count": len(surveys),
        "published_count": published_count,
        "draft_count": draft_count,
        "private_count": private_count,
        "total_responses": total_responses,
        "average_responses": average_responses,
        "recent_surveys": recent_surveys,
        "live_surveys": live_surveys,
        "draft_surveys": draft_surveys,
        "recent_responses": recent_responses,
    }
    return render(request, "survey/creator/creator_dashboard.html", context)


@role_required(allowed_roles=["creator"])
def CreateSurveyPageView(request):
    drafts = (
        Survey.objects.filter(created_by=request.user, is_published=False)
        .order_by("-updated_at")
    )
    templates = SurveyTemplate.objects.filter(is_active=True).order_by("-created_at")[:6]
    return render(
        request,
        "survey/creator/create_survey_page.html",
        {
            "drafts": drafts,
            "draft_count": drafts.count(),
            "templates": templates,
        },
    )


@role_required(allowed_roles=["creator"])
@require_GET
def SurveyBuilderView(request, survey_id=None):
    survey = None
    bootstrap = {
        "survey_id": None,
        "title": "Untitled Survey",
        "description": "",
        "mode": "regular",
        "visibility": "public",
        "theme": DEFAULT_THEME,
        "settings": DEFAULT_SETTINGS,
        "questions": [],
        "canvas_elements": [],
        "is_published": False,
        "share_url": "",
        "preview_url": "",
        "publish_url": "",
        "unpublish_url": "",
        "save_url": "",
        "qr_svg": "",
    }

    if survey_id is not None:
        survey = get_object_or_404(_survey_queryset(), pk=survey_id, created_by=request.user)
        bootstrap = _serialize_survey(request, survey)

    return render(
        request,
        "survey/creator/create_survey_builder.html",
        {
            "survey": survey,
            "builder_bootstrap": bootstrap,
            "hide_navbar": True,
            "hide_footer": True,
        },
    )


@role_required(allowed_roles=["creator"])
@require_POST
def create_survey(request):
    payload = _parse_json_body(request)
    if payload is None:
        return _json_error("Invalid JSON payload.")

    survey = Survey.objects.create(
        title=(payload.get("title") or "").strip() or "Untitled Survey",
        description=payload.get("description", ""),
        survey_type=_normalize_mode(payload.get("mode")),
        visibility=_normalize_visibility(payload.get("visibility")),
        created_by=request.user,
        theme=DEFAULT_THEME | (payload.get("theme") or {}),
        settings=_client_settings(DEFAULT_SETTINGS | (payload.get("settings") or {})),
    )
    survey.share_url = _build_share_url(request, survey)
    survey.save(update_fields=["share_url", "updated_at"])

    return JsonResponse(
        {
            "status": "success",
            "survey_id": survey.id,
            "builder_url": reverse("survey_builder_edit", kwargs={"survey_id": survey.id}),
            "save_url": reverse("save_survey", kwargs={"survey_id": survey.id}),
            "publish_url": reverse("publish_survey", kwargs={"survey_id": survey.id}),
            "unpublish_url": reverse("unpublish_survey", kwargs={"survey_id": survey.id}),
            "preview_url": reverse("survey_preview", kwargs={"survey_id": survey.id}),
            "share_url": survey.share_url,
        }
    )


@role_required(allowed_roles=["creator"])
@require_POST
def save_survey(request, survey_id):
    survey = get_object_or_404(Survey, pk=survey_id, created_by=request.user)
    payload = _parse_json_body(request)
    if payload is None:
        return _json_error("Invalid JSON payload.")

    serialized = _persist_survey_payload(request, survey, payload, publish=False)
    return JsonResponse(
        {
            "status": "success",
            "message": "Survey saved successfully.",
            "survey": serialized,
        }
    )


@role_required(allowed_roles=["creator"])
@require_POST
def publish_survey(request, survey_id):
    survey = get_object_or_404(Survey, pk=survey_id, created_by=request.user)
    payload = _parse_json_body(request)
    if payload is None:
        return _json_error("Invalid JSON payload.")

    try:
        serialized = _persist_survey_payload(
            request,
            survey,
            payload,
            publish=True,
            force_publish_state=True,
        )
    except ValueError as exc:
        return _json_error(str(exc))

    return JsonResponse(
        {
            "status": "success",
            "message": "Survey published successfully.",
            "survey": serialized,
        }
    )


@role_required(allowed_roles=["creator"])
@require_POST
def unpublish_survey(request, survey_id):
    survey = get_object_or_404(Survey, pk=survey_id, created_by=request.user)
    payload = _parse_json_body(request)
    if payload is None:
        return _json_error("Invalid JSON payload.")

    serialized = _persist_survey_payload(
        request,
        survey,
        payload,
        publish=False,
        force_publish_state=False,
    )
    return JsonResponse(
        {
            "status": "success",
            "message": "Survey unpublished successfully.",
            "survey": serialized,
        }
    )


@role_required(allowed_roles=["creator"])
@require_GET
def survey_preview(request, survey_id):
    survey = get_object_or_404(_survey_queryset(), pk=survey_id, created_by=request.user)
    preview_context = _build_preview_context(survey, preview_mode=True)
    return render(
        request,
        "survey/creator/survey_preview.html",
        {
            "survey": survey,
            "survey_payload": _serialize_survey(request, survey),
            "preview_mode": True,
            "hide_navbar": True,
            "hide_footer": True,
            **preview_context,
        },
    )


def public_survey_detail(request, share_token):
    survey = get_object_or_404(
        _survey_queryset(),
        share_token=share_token,
        is_published=True,
    )
    is_private = survey.visibility == "private"
    survey_password_hash = _survey_password_hash(survey)

    if is_private and not request.user.is_authenticated:
        login_query = urlencode({"next": request.get_full_path()})
        return redirect(f"{reverse('login')}?{login_query}")

    has_private_access = not is_private or _has_private_access(request, survey)

    if is_private and request.method == "POST" and request.POST.get("form_type") == "private_access":
        submitted_password = (request.POST.get("survey_password") or "").strip()
        if survey_password_hash and check_password(submitted_password, survey_password_hash):
            _set_private_access(request, survey)
            messages.success(request, _("Private survey unlocked successfully."))
            return redirect("public_survey_detail", share_token=share_token)

        messages.error(request, _("Incorrect survey password."))
        return redirect("public_survey_detail", share_token=share_token)

    if is_private and not has_private_access:
        preview_context = _build_preview_context(survey, preview_mode=False)
        return render(
            request,
            "survey/creator/survey_preview.html",
            {
                "survey": survey,
                "survey_payload": _serialize_survey(request, survey),
                "preview_mode": False,
                "show_private_access_gate": True,
                "hide_navbar": True,
                "hide_footer": True,
                **preview_context,
            },
        )

    if request.method == "POST":
        answers, errors = _collect_response_answers(request, survey)
        if errors:
            for error in errors:
                messages.error(request, error)
        else:
            response_payload = {
                "submitted_via": "public_share_link",
                "answers": answers,
            }
            if request.user.is_authenticated:
                response_payload["respondent"] = {
                    "user_id": request.user.id,
                    "name": _get_user_display_name(request.user),
                    "email": request.user.email,
                }

            Response.objects.create(
                survey=survey,
                user=request.user if request.user.is_authenticated else None,
                answers=response_payload,
            )
            messages.success(request, _("Your response has been submitted successfully."))
            return redirect("public_survey_detail", share_token=share_token)

    preview_context = _build_preview_context(survey, preview_mode=False)
    return render(
        request,
        "survey/creator/survey_preview.html",
        {
            "survey": survey,
            "survey_payload": _serialize_survey(request, survey),
            "preview_mode": False,
            "show_private_access_gate": False,
            "hide_navbar": True,
            "hide_footer": True,
            **preview_context,
        },
    )


@role_required(allowed_roles=["creator"])
def MySurveysView(request):
    surveys = (
        Survey.objects.filter(created_by=request.user)
        .annotate(
            question_count=Count("questions", distinct=True),
            response_count=Count("responses", distinct=True),
        )
        .order_by("-updated_at")
    )
    context = {
        "surveys": surveys,
        "survey_count": surveys.count(),
        "published_count": surveys.filter(is_published=True).count(),
        "draft_count": surveys.filter(is_published=False).count(),
        "private_count": surveys.filter(visibility="private").count(),
        "response_total": sum(survey.response_count for survey in surveys),
    }
    return render(request, "survey/creator/my_surveys.html", context)


@role_required(allowed_roles=["creator"])
def AnalyticsView(request):
    surveys = list(
        Survey.objects.filter(created_by=request.user)
        .annotate(
            question_count=Count("questions", distinct=True),
            response_count=Count("responses", distinct=True),
        )
        .prefetch_related(
            Prefetch("questions", queryset=Question.objects.prefetch_related("options")),
            "responses",
        )
        .order_by("-updated_at")
    )

    now = timezone.localtime()
    survey_map = {survey.id: survey for survey in surveys}
    selected_survey = None
    selected_survey_id = request.GET.get("survey")
    if selected_survey_id and selected_survey_id.isdigit():
        selected_survey = survey_map.get(int(selected_survey_id))
    if selected_survey is None and surveys:
        selected_survey = surveys[0]

    date_range = request.GET.get("range", "all")
    custom_start_raw = (request.GET.get("start") or "").strip()
    custom_end_raw = (request.GET.get("end") or "").strip()
    selected_question_id = request.GET.get("question", "all")

    range_options = {
        "today": {"label": "Today", "days": 1},
        "7d": {"label": "Last 7 days", "days": 7},
        "30d": {"label": "Last 30 days", "days": 30},
        "90d": {"label": "Last 90 days", "days": 90},
        "all": {"label": "All time", "days": None},
        "custom": {"label": "Custom range", "days": None},
    }
    if date_range not in range_options:
        date_range = "all"

    start_at = None
    end_at = None
    if date_range == "today":
        start_at = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_at = now
    elif range_options[date_range]["days"]:
        start_at = now - timedelta(days=range_options[date_range]["days"] - 1)
        end_at = now
    elif date_range == "custom":
        try:
            if custom_start_raw:
                start_at = timezone.make_aware(
                    datetime.fromisoformat(custom_start_raw).replace(hour=0, minute=0, second=0, microsecond=0)
                )
            if custom_end_raw:
                end_at = timezone.make_aware(
                    datetime.fromisoformat(custom_end_raw).replace(hour=23, minute=59, second=59, microsecond=999999)
                )
        except ValueError:
            start_at = None
            end_at = None

    total_surveys = len(surveys)
    total_responses = sum(survey.response_count for survey in surveys)
    published_count = sum(1 for survey in surveys if survey.is_published)
    draft_count = total_surveys - published_count
    private_count = sum(1 for survey in surveys if survey.visibility == "private")
    public_count = total_surveys - private_count
    average_responses = round(total_responses / total_surveys, 1) if total_surveys else 0

    top_surveys = sorted(surveys, key=lambda survey: (-survey.response_count, survey.title.lower()))[:5]

    response_trend_counter = defaultdict(int)
    all_recent_responses = []
    for survey in surveys:
        survey_recent_responses = list(survey.responses.all())
        all_recent_responses.extend(survey_recent_responses)
        for response in survey_recent_responses:
            response_trend_counter[response.submitted_at.date()] += 1

    all_recent_responses.sort(key=lambda response: response.submitted_at, reverse=True)
    recent_responses = []
    for response in all_recent_responses[:6]:
        recent_responses.append(
            {
                "survey_title": response.survey.title,
                "respondent_name": (
                    _get_user_display_name(response.user)
                    if response.user
                    else "Anonymous respondent"
                ),
                "submitted_at": response.submitted_at,
                "answer_count": len(_response_answer_items(response)),
            }
        )

    selected_questions = []
    selected_summary = None
    filter_meta = {
        "date_range": date_range,
        "date_range_label": range_options[date_range]["label"],
        "custom_start": custom_start_raw,
        "custom_end": custom_end_raw,
        "selected_question": selected_question_id,
        "question_options": [],
        "device_tracking_enabled": False,
        "location_tracking_enabled": False,
    }
    selected_overview = None
    audience_insights = []
    engagement_metrics = []
    export_actions = []
    chart_data = {
        "surveyLabels": [survey.title for survey in top_surveys],
        "surveyResponses": [survey.response_count for survey in top_surveys],
        "visibilityLabels": ["Public", "Private"],
        "visibilityValues": [public_count, private_count],
        "responseTrendLabels": [date.strftime("%d %b") for date, _ in sorted(response_trend_counter.items())][-8:],
        "responseTrendValues": [value for _, value in sorted(response_trend_counter.items())][-8:],
        "selectedTrendLines": {"daily": {"labels": [], "values": []}, "weekly": {"labels": [], "values": []}, "monthly": {"labels": [], "values": []}},
        "selectedResponseBars": {"labels": [], "values": []},
        "questionCharts": [],
        "dropoffHeatmap": [],
        "csvExport": {
            "surveyTitle": "",
            "exportDate": timezone.localtime().date().isoformat(),
            "headers": [],
            "rows": [],
        },
        "excelExport": {
            "summary": {},
            "trendRows": [],
            "questionAnalysis": [],
            "audienceInsights": [],
        },
        "pdfExport": {
            "cover": {},
            "keyMetrics": {},
            "trend": {},
            "audienceInsights": [],
            "insightsSummary": {},
        },
    }

    if selected_survey:
        all_selected_responses = list(selected_survey.responses.all())
        selected_responses = []
        for response in all_selected_responses:
            submitted_at = timezone.localtime(response.submitted_at)
            if start_at and submitted_at < start_at:
                continue
            if end_at and submitted_at > end_at:
                continue
            selected_responses.append(response)

        selected_questions_queryset = list(selected_survey.questions.all())
        selected_answer_maps = [_response_answer_lookup(response) for response in selected_responses]
        filter_meta["question_options"] = [
            {
                "id": str(question.id),
                "label": f"Q{index}. {question.question_text[:60]}",
            }
            for index, question in enumerate(selected_questions_queryset, start=1)
        ]
        csv_question_headers = [f"Q{index}" for index, _ in enumerate(selected_questions_queryset, start=1)]
        chart_data["csvExport"] = {
            "surveyTitle": selected_survey.title,
            "exportDate": timezone.localtime().date().isoformat(),
            "headers": ["Response ID", "User", "Start Time", "End Time", "Duration", "Status", *csv_question_headers],
            "rows": [],
        }

        required_question_ids = {question.id for question in selected_questions_queryset if question.is_required}
        for response, answer_map in zip(selected_responses, selected_answer_maps):
            response_meta = response.answers if isinstance(response.answers, dict) else {}
            started_at = (
                response_meta.get("start_time")
                or response_meta.get("started_at")
                or response_meta.get("started_time")
            )
            completed_at = (
                response_meta.get("end_time")
                or response_meta.get("completed_at")
                or response_meta.get("submitted_at")
                or response.submitted_at
            )
            duration = response_meta.get("duration") or response_meta.get("duration_text") or "-"

            answered_required_ids = {
                question_id
                for question_id, answer in answer_map.items()
                if question_id in required_question_ids and answer.get("value") not in ("", [], {}, None)
            }
            response_status = "Completed" if answered_required_ids == required_question_ids else "Partial"

            response_row = [
                response.id,
                _get_user_display_name(response.user) if response.user else f"Anonymous-{response.id}",
                _format_export_datetime(started_at),
                _format_export_datetime(completed_at),
                duration,
                response_meta.get("status") or response_status,
            ]
            for question in selected_questions_queryset:
                answer = answer_map.get(question.id)
                response_row.append(_format_answer_value(answer.get("value")) if answer else "-")

            chart_data["csvExport"]["rows"].append(response_row)

        total_required_answers = sum(1 for question in selected_questions_queryset if question.is_required) * len(selected_responses)
        completed_required_answers = 0
        selected_trend_daily = defaultdict(int)
        selected_trend_weekly = defaultdict(int)
        selected_trend_monthly = defaultdict(int)
        response_hour_counter = Counter()
        authenticated_responder_counter = Counter()

        for response in selected_responses:
            submitted_at = timezone.localtime(response.submitted_at)
            selected_trend_daily[submitted_at.date()] += 1
            week_start = submitted_at.date() - timedelta(days=submitted_at.weekday())
            selected_trend_weekly[week_start] += 1
            month_start = submitted_at.date().replace(day=1)
            selected_trend_monthly[month_start] += 1
            response_hour_counter[submitted_at.hour] += 1
            if response.user_id:
                authenticated_responder_counter[response.user_id] += 1

        def _serialize_trend(counter, label_format):
            items = sorted(counter.items())
            return {
                "labels": [label_format(item_key) for item_key, _ in items],
                "values": [value for _, value in items],
            }

        chart_data["selectedTrendLines"] = {
            "daily": _serialize_trend(selected_trend_daily, lambda value: value.strftime("%d %b")),
            "weekly": _serialize_trend(selected_trend_weekly, lambda value: f"Week of {value.strftime('%d %b')}"),
            "monthly": _serialize_trend(selected_trend_monthly, lambda value: value.strftime("%b %Y")),
        }
        chart_data["selectedResponseBars"] = _serialize_trend(selected_trend_daily, lambda value: value.strftime("%d %b"))

        filtered_question_count = 0

        for question_index, question in enumerate(selected_questions_queryset, start=1):
            option_labels = [option.option_text for option in question.options.all()]
            answer_values = []
            answer_total = 0

            for answer_map in selected_answer_maps:
                answer = answer_map.get(question.id)
                if not answer:
                    continue

                raw_value = answer.get("value")
                if raw_value in ("", [], {}, None):
                    continue

                answer_total += 1
                answer_values.append(raw_value)
                if question.is_required:
                    completed_required_answers += 1

            drop_off_rate = round(100 - ((answer_total / len(selected_responses)) * 100), 1) if selected_responses else 0
            question_data = {
                "id": question.id,
                "question_number": question_index,
                "question_text": question.question_text,
                "question_type": question.get_question_type_display(),
                "is_required": question.is_required,
                "answer_total": answer_total,
                "response_rate": round((answer_total / len(selected_responses)) * 100, 1) if selected_responses else 0,
                "drop_off_rate": drop_off_rate,
                "visual_type": "samples",
                "segments": [],
                "sample_answers": [],
                "average_rating": None,
                "top_option": None,
                "text_cloud": [],
            }

            if question.question_type in {"multiple_choice", "dropdown"}:
                counts = Counter(value for value in answer_values if isinstance(value, str))
                question_data["visual_type"] = "distribution"
                question_data["segments"] = [
                    {
                        "label": label,
                        "count": counts.get(label, 0),
                        "width": round((counts.get(label, 0) / answer_total) * 100, 1) if answer_total else 0,
                    }
                    for label in option_labels
                ]
                if counts:
                    top_option = counts.most_common(1)[0]
                    question_data["top_option"] = f"{top_option[0]} ({top_option[1]})"
            elif question.question_type == "checkboxes":
                counts = Counter()
                for value in answer_values:
                    if isinstance(value, list):
                        counts.update(value)
                question_data["visual_type"] = "distribution"
                question_data["segments"] = [
                    {
                        "label": label,
                        "count": counts.get(label, 0),
                        "width": round((counts.get(label, 0) / answer_total) * 100, 1) if answer_total else 0,
                    }
                    for label in option_labels
                ]
                if counts:
                    top_option = counts.most_common(1)[0]
                    question_data["top_option"] = f"{top_option[0]} ({top_option[1]})"
            elif question.question_type == "rating":
                rating_max = int((question.settings or {}).get("rating_max") or 5)
                counts = Counter(int(value) for value in answer_values if isinstance(value, int))
                question_data["visual_type"] = "distribution"
                question_data["segments"] = [
                    {
                        "label": f"{rating} star",
                        "count": counts.get(rating, 0),
                        "width": round((counts.get(rating, 0) / answer_total) * 100, 1) if answer_total else 0,
                    }
                    for rating in range(1, rating_max + 1)
                ]
                question_data["average_rating"] = round(
                    sum(int(value) for value in answer_values if isinstance(value, int)) / answer_total,
                    1,
                ) if answer_total else None
            else:
                formatted_samples = []
                question_word_frequency = Counter()
                for value in answer_values[:4]:
                    formatted_value = _format_answer_value(value)
                    formatted_samples.append(formatted_value)
                    for token in re.findall(r"[A-Za-z]{3,}", formatted_value.lower()):
                        question_word_frequency[token] += 1
                question_data["sample_answers"] = formatted_samples
                question_data["text_cloud"] = [
                    {"label": label, "count": count}
                    for label, count in question_word_frequency.most_common(10)
                ]

            if selected_question_id not in {"", "all"} and str(question.id) != str(selected_question_id):
                continue

            filtered_question_count += 1
            if question_data["visual_type"] == "distribution":
                chart_data["questionCharts"].append(
                    {
                        "questionId": question.id,
                        "questionType": question.question_type,
                        "labels": [segment["label"] for segment in question_data["segments"]],
                        "values": [segment["count"] for segment in question_data["segments"]],
                    }
                )

            selected_questions.append(question_data)
            chart_data["dropoffHeatmap"].append(
                {
                    "questionNumber": question_index,
                    "questionText": question.question_text,
                    "dropoff": drop_off_rate,
                    "responseRate": question_data["response_rate"],
                }
            )

        completion_rate = round(
            (completed_required_answers / total_required_answers) * 100,
            1,
        ) if total_required_answers else 100
        drop_off_rate = round(100 - completion_rate, 1)

        response_dates = sorted(timezone.localtime(response.submitted_at) for response in selected_responses)
        first_response_date = response_dates[0] if response_dates else None
        last_response_date = response_dates[-1] if response_dates else None
        peak_hour = response_hour_counter.most_common(1)[0][0] if response_hour_counter else None
        peak_response_time = (
            datetime(2000, 1, 1, peak_hour, 0).strftime("%I:%M %p")
            if peak_hour is not None
            else "No responses yet"
        )

        returning_users = sum(1 for count in authenticated_responder_counter.values() if count > 1)
        new_users = sum(1 for count in authenticated_responder_counter.values() if count == 1)
        anonymous_users = len(selected_responses) - sum(authenticated_responder_counter.values())

        selected_summary = {
            "id": selected_survey.id,
            "title": selected_survey.title,
            "description": selected_survey.description,
            "created_at": selected_survey.created_at,
            "is_published": selected_survey.is_published,
            "visibility": selected_survey.visibility,
            "survey_type": selected_survey.get_survey_type_display(),
            "question_count": selected_survey.question_count,
            "response_count": len(selected_responses),
            "total_response_count": selected_survey.response_count,
            "completion_rate": completion_rate,
            "drop_off_rate": drop_off_rate,
            "updated_at": selected_survey.updated_at,
            "share_url": selected_survey.share_url,
            "active_status": "Live" if selected_survey.is_published else "Closed",
            "views_available": False,
            "average_time_available": False,
            "first_response_date": first_response_date,
            "last_response_date": last_response_date,
            "peak_response_time": peak_response_time,
            "question_filter_count": filtered_question_count,
        }

        selected_overview = [
            {"label": "First response", "value": first_response_date.strftime("%d %b %Y, %I:%M %p") if first_response_date else "No responses yet"},
            {"label": "Last response", "value": last_response_date.strftime("%d %b %Y, %I:%M %p") if last_response_date else "No responses yet"},
            {"label": "Peak response time", "value": peak_response_time},
            {"label": "Questions in view", "value": str(filtered_question_count or len(selected_questions_queryset))},
        ]

        audience_insights = [
            {"label": "Device type", "value": "Tracking not enabled", "description": "Capture device metadata during submission to unlock mobile vs desktop insight."},
            {"label": "Browser", "value": "Tracking not enabled", "description": "Browser analytics can appear here once user-agent tracking is added."},
            {"label": "Location", "value": "Tracking not enabled", "description": "City and country insight need IP or geo capture in the response pipeline."},
            {"label": "New vs returning", "value": f"{new_users} new / {returning_users} returning", "description": f"{anonymous_users} anonymous response{'s' if anonymous_users != 1 else ''} are excluded from the returning-user check."},
        ]

        engagement_metrics = [
            {"label": "Start rate", "value": "Unavailable", "description": "Survey views are not tracked in the current data model."},
            {"label": "Completion rate", "value": f"{completion_rate}%", "description": "Calculated from required-question coverage across filtered responses."},
            {"label": "Drop-off rate", "value": f"{drop_off_rate}%", "description": "Inverse of completion rate for the active response filter."},
            {"label": "Highest drop-off", "value": f"Q{max(chart_data['dropoffHeatmap'], key=lambda item: item['dropoff'])['questionNumber']}" if chart_data["dropoffHeatmap"] else "N/A", "description": "Pinpoints the question where the biggest response loss appears."},
        ]

        export_actions = [
            {"id": "exportCsv", "label": "Export CSV", "icon": "file-spreadsheet"},
            {"id": "downloadCharts", "label": "Download Charts", "icon": "download"},
            {"id": "printReport", "label": "Print Report", "icon": "printer"},
        ]

        peak_trend_label = "No response day yet"
        peak_trend_value = 0
        if chart_data["selectedResponseBars"]["labels"] and chart_data["selectedResponseBars"]["values"]:
            peak_index = max(
                range(len(chart_data["selectedResponseBars"]["values"])),
                key=lambda index: chart_data["selectedResponseBars"]["values"][index],
            )
            peak_trend_label = chart_data["selectedResponseBars"]["labels"][peak_index]
            peak_trend_value = chart_data["selectedResponseBars"]["values"][peak_index]

        top_option_candidates = []
        for question in selected_questions:
            top_option = question.get("top_option")
            if not top_option:
                continue
            try:
                option_label, count_text = top_option.rsplit("(", 1)
                option_count = int(count_text.rstrip(")"))
            except (ValueError, AttributeError):
                continue
            top_option_candidates.append(
                {
                    "question_text": question["question_text"],
                    "option_label": option_label.strip(),
                    "count": option_count,
                }
            )

        best_option = max(top_option_candidates, key=lambda item: item["count"]) if top_option_candidates else None
        highest_dropoff = max(chart_data["dropoffHeatmap"], key=lambda item: item["dropoff"]) if chart_data["dropoffHeatmap"] else None
        observations = [
            f"{len(selected_responses)} response{'s' if len(selected_responses) != 1 else ''} are included in this report.",
            f"Completion rate is {completion_rate}% for the active analytics view.",
            (
                f"Peak response day was {peak_trend_label} with {peak_trend_value} response{'s' if peak_trend_value != 1 else ''}."
                if peak_trend_value
                else "No peak response day is available yet."
            ),
        ]

        chart_data["pdfExport"] = {
            "cover": {
                "surveyTitle": selected_survey.title,
                "description": selected_survey.description or "No description added yet.",
                "createdBy": _get_user_display_name(request.user),
                "exportDate": timezone.localtime().strftime("%Y-%m-%d"),
            },
            "keyMetrics": {
                "totalResponses": len(selected_responses),
                "totalViews": "Unavailable",
                "completionRate": f"{completion_rate}%",
                "avgTime": "Unavailable",
                "dropOffRate": f"{drop_off_rate}%",
            },
            "trend": {
                "peakResponseDay": peak_trend_label,
                "peakResponseCount": peak_trend_value,
            },
            "audienceInsights": [
                {
                    "label": item["label"],
                    "value": item["value"],
                    "description": item["description"],
                }
                for item in audience_insights
            ],
            "insightsSummary": {
                "mostSelectedOption": (
                    f"{best_option['option_label']} ({best_option['count']}) in {best_option['question_text']}"
                    if best_option
                    else "No option trend available yet"
                ),
                "dropOffQuestion": (
                    f"Q{highest_dropoff['questionNumber']} - {highest_dropoff['questionText']}"
                    if highest_dropoff
                    else "No drop-off question yet"
                ),
                "observations": observations,
            },
        }

        chart_data["excelExport"] = {
            "summary": {
                "surveyTitle": selected_survey.title,
                "createdDate": timezone.localtime(selected_survey.created_at).strftime("%Y-%m-%d"),
                "totalResponses": len(selected_responses),
                "totalViews": "Unavailable",
                "completionRate": f"{completion_rate}%",
                "dropOffRate": f"{drop_off_rate}%",
                "averageTime": "Unavailable",
            },
            "trendRows": [
                {"date": label, "responses": value}
                for label, value in zip(
                    chart_data["selectedResponseBars"]["labels"],
                    chart_data["selectedResponseBars"]["values"],
                )
            ],
            "questionAnalysis": [
                {
                    "questionText": question["question_text"],
                    "questionType": question["question_type"],
                    "rows": (
                        [
                            {
                                "label": segment["label"],
                                "count": segment["count"],
                                "percentage": f"{segment['width']}%",
                            }
                            for segment in question["segments"]
                        ]
                        if question["visual_type"] == "distribution"
                        else [
                            {
                                "label": sample,
                                "count": "",
                                "percentage": "",
                            }
                            for sample in question["sample_answers"]
                        ]
                    ),
                }
                for question in selected_questions
            ],
            "audienceInsights": [
                {
                    "label": item["label"],
                    "value": item["value"],
                    "description": item["description"],
                }
                for item in audience_insights
            ],
        }

    context = {
        "surveys": surveys,
        "selected_survey": selected_summary,
        "selected_questions": selected_questions,
        "survey_count": total_surveys,
        "published_count": published_count,
        "draft_count": draft_count,
        "private_count": private_count,
        "total_responses": total_responses,
        "average_responses": average_responses,
        "top_surveys": top_surveys,
        "recent_responses": recent_responses,
        "chart_data": chart_data,
        "filter_meta": filter_meta,
        "selected_overview": selected_overview,
        "audience_insights": audience_insights,
        "engagement_metrics": engagement_metrics,
        "export_actions": export_actions,
    }
    return render(request, "survey/creator/analytics.html", context)


# ========================================================================================================
# Respondent
# ========================================================================================================

@role_required(allowed_roles=["respondent"])
def RespondentDashboardView(request):
    available_surveys = Survey.objects.filter(is_published=True).exclude(created_by=request.user)
    my_responses = Response.objects.filter(user=request.user).select_related("survey")
    return render(
        request,
        "survey/respondent/respondent_dashboard.html",
        {
            "available_survey_count": available_surveys.count(),
            "response_count": my_responses.count(),
            "recent_responses": my_responses[:5],
        },
    )


@role_required(allowed_roles=["respondent"])
def AvailableSurveysView(request):
    surveys = Survey.objects.filter(is_published=True).exclude(created_by=request.user)
    return render(request, "survey/respondent/available_surveys.html", {"surveys": surveys})


@role_required(allowed_roles=["respondent"])
def MyResponsesView(request):
    responses = Response.objects.filter(user=request.user).select_related("survey")
    for response in responses:
        answer_items = response.answers.get("answers", []) if isinstance(response.answers, dict) else []
        for answer in answer_items:
            answer["display_value"] = _format_answer_value(answer.get("value"))
    return render(request, "survey/respondent/my_responses.html", {"responses": responses})


@role_required(allowed_roles=["respondent"])
def ProfileView(request):
    if request.method == "POST":
        form = RespondentProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            updated_user = form.save(commit=False)
            updated_user.email = request.user.email
            updated_user.role = request.user.role
            updated_user.save(update_fields=["first_name", "last_name", "gender", "phone_no", "updated_at"])
            messages.success(request, "Profile updated successfully.")
            return redirect("profile")
    else:
        form = RespondentProfileForm(instance=request.user)

    return render(request, "survey/respondent/profile.html", {"form": form})
