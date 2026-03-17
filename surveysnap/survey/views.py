from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db.models import Count
from django.db.models.functions import TruncMonth
from .decorators import role_required
from core.models import User
from survey.models import *
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages

# Create your views here.


# Admin :

# @login_required(login_url="login") 
@role_required(allowed_roles=["admin"])
def AdminDashboardView(request):
    # =====================
    # USERS
    # =====================
    creators = User.objects.filter(role="creator").count()
    respondents = User.objects.filter(role="respondent").count()
    admins = User.objects.filter(role="admin").count()

    # =====================
    # SURVEYS
    # =====================
    surveys = Survey.objects.count()

    draft_surveys = Survey.objects.filter(status="Draft").count()
    active_surveys = Survey.objects.filter(status="Active").count()
    closed_surveys = Survey.objects.filter(status="Closed").count()

    # =====================
    # SURVEY TEMPLATES
    # =====================
    templates = SurveyTemplate.objects.count()

    system_templates = SurveyTemplate.objects.filter(
        is_system_template=True
    ).count()

    creator_templates = SurveyTemplate.objects.filter(
        is_system_template=False
    ).count()

    # Templates by Category
    template_categories = (
        SurveyTemplate.objects
        .values("category")
        .annotate(total=Count("id"))
        .order_by("-total")
    )

    categories = []
    category_counts = []

    for item in template_categories:
        categories.append(item["category"])
        category_counts.append(item["total"])

    # =====================
    # MONTHLY SURVEY GROWTH
    # =====================
    monthly_surveys = (
        Survey.objects
        .annotate(month=TruncMonth("created_at"))
        .values("month")
        .annotate(total=Count("id"))
        .order_by("month")
    )

    months = []
    survey_counts = []

    for item in monthly_surveys:
        months.append(item["month"].strftime("%b"))
        survey_counts.append(item["total"])

    # =====================
    # TOP CREATORS
    # =====================
    top_creators = (
        Survey.objects
        .values("creator__first_name", "creator__last_name")
        .annotate(total=Count("id"))
        .order_by("-total")[:5]
    )

    # =====================
    # TOP TEMPLATE CREATORS
    # =====================
    top_template_creators = (
        SurveyTemplate.objects
        
        .values("creator__first_name", "creator__last_name")
        .annotate(total=Count("id"))
        .order_by("-total")[:5]
    )

    # =====================
    # RECENT DATA
    # =====================
    recent_surveys = Survey.objects.select_related("creator").order_by("-created_at")[:5]

    recent_templates = SurveyTemplate.objects.order_by("-created_at")[:5]

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

        "categories": categories,
        "category_counts": category_counts,

        "months": months,
        "survey_counts": survey_counts,

        "top_creators": top_creators,
        "top_template_creators": top_template_creators,

        "recent_surveys": recent_surveys,
        "recent_templates": recent_templates,
    }

    return render(request,"survey/admin/admin_dashboard.html",context)

    
@role_required(allowed_roles=["admin"])
def MangeUsersView(request):
    search = request.GET.get("search")

    if search:
        users = User.objects.filter(email__icontains=search)
    else:
        users = User.objects.all().order_by("-id")

    context = {
        "users": users
    }

    return render(request, "survey/admin/manage_users.html", context)

@role_required(allowed_roles=["admin"])
def add_user(request):

    if request.method == "POST":

        user = User.objects.create_user(
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

    user = get_object_or_404(User, id=id)
    user.delete()

    messages.success(request, "User deleted successfully")
    return redirect("manage_users")


@role_required(allowed_roles=["admin"])
def MangeSurveysView(request):
    return render(request,"survey/admin/manage_surveys.html")

@role_required(allowed_roles=["admin"])
def ManageTemplatesView(request):
    return render(request,"survey/admin/manage_templates.html")

@role_required(allowed_roles=["admin"])
def ReportsView(request):
    return render(request,"survey/admin/reports.html")


# Survey Creator :

# @login_required(login_url="login")
@role_required(allowed_roles=["creator"])
def CreatorDashboardView(request):
    return render(request,"survey/creator/creator_dashboard.html")

@role_required(allowed_roles=["creator"])
def CreateSurveyView(request):
    return render(request,"survey/creator/create_survey.html")

@role_required(allowed_roles=["creator"])
def MySurveysView(request):
    return render(request,"survey/creator/my_surveys.html")

@role_required(allowed_roles=["creator"])
def AnalyticsView(request):
    return render(request,"survey/creator/analytics.html")

# Respodent :

# @login_required(login_url="login")
@role_required(allowed_roles=["respondent"])
def RespondentDashboardView(request):
    return render(request,"survey/respondent/respondent_dashboard.html")

@role_required(allowed_roles=["respondent"])
def AvailableSurveysView(request):
    return render(request,"survey/respondent/available_surveys.html")

@role_required(allowed_roles=["respondent"])
def MyResponsesView(request):
    return render(request,"survey/respondent/my_responses.html")

@role_required(allowed_roles=["respondent"])
def ProfileView(request):
    return render(request,"survey/respondent/profile.html")