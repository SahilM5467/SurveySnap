import json
from io import BytesIO

from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Prefetch
from django.db.models.functions import TruncMonth
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_GET, require_POST

from core.models import User

from .decorators import role_required
from .models import CanvasElement, Option, Question, Survey, SurveyTemplate

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

    return {
        "title": title,
        "description": payload.get("description", ""),
        "mode": _normalize_mode(payload.get("mode")),
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
        "theme": DEFAULT_THEME | (survey.theme or {}),
        "settings": DEFAULT_SETTINGS | (survey.settings or {}),
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


@transaction.atomic
def _persist_survey_payload(request, survey, payload, publish=False, force_publish_state=None):
    validated = _validate_payload(payload, for_publish=publish)
    share_url = _build_share_url(request, survey)

    survey.title = validated["title"]
    survey.description = validated["description"]
    survey.survey_type = validated["mode"]
    survey.theme = validated["theme"]
    survey.settings = validated["settings"]
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
        "settings": validated["settings"],
    }
    survey.save(
        update_fields=[
            "title",
            "description",
            "survey_type",
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


# ===========================================================
# Admin
# ===========================================================

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


# ===========================================================
# Survey Creator
# ===========================================================

@role_required(allowed_roles=["creator"])
def CreatorDashboardView(request):
    return render(request, "survey/creator/creator_dashboard.html")


@role_required(allowed_roles=["creator"])
def CreateSurveyPageView(request):
    drafts = (
        Survey.objects.filter(created_by=request.user, is_published=False)
        .order_by("-updated_at")[:6]
    )
    templates = SurveyTemplate.objects.filter(is_active=True).order_by("-created_at")[:6]
    return render(
        request,
        "survey/creator/create_survey_page.html",
        {"drafts": drafts, "templates": templates},
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
        created_by=request.user,
        theme=DEFAULT_THEME | (payload.get("theme") or {}),
        settings=DEFAULT_SETTINGS | (payload.get("settings") or {}),
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
    return render(
        request,
        "survey/creator/survey_preview.html",
        {
            "survey": survey,
            "survey_payload": _serialize_survey(request, survey),
            "preview_mode": True,
        },
    )


@require_GET
def public_survey_detail(request, share_token):
    survey = get_object_or_404(
        _survey_queryset(),
        share_token=share_token,
        is_published=True,
    )
    return render(
        request,
        "survey/creator/survey_preview.html",
        {
            "survey": survey,
            "survey_payload": _serialize_survey(request, survey),
            "preview_mode": False,
        },
    )


@role_required(allowed_roles=["creator"])
def MySurveysView(request):
    surveys = Survey.objects.filter(created_by=request.user).order_by("-updated_at")
    return render(request, "survey/creator/my_surveys.html", {"surveys": surveys})


@role_required(allowed_roles=["creator"])
def AnalyticsView(request):
    return render(request, "survey/creator/analytics.html")


# ===========================================================
# Respondent
# ===========================================================

@role_required(allowed_roles=["respondent"])
def RespondentDashboardView(request):
    return render(request, "survey/respondent/respondent_dashboard.html")


@role_required(allowed_roles=["respondent"])
def AvailableSurveysView(request):
    return render(request, "survey/respondent/available_surveys.html")


@role_required(allowed_roles=["respondent"])
def MyResponsesView(request):
    return render(request, "survey/respondent/my_responses.html")


@role_required(allowed_roles=["respondent"])
def ProfileView(request):
    return render(request, "survey/respondent/profile.html")
