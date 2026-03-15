from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .decorators import role_required
from core.models import User
from survey.models import Survey, Response

# Create your views here.


# Admin :

# @login_required(login_url="login") 
@role_required(allowed_roles=["admin"])
def AdminDashboardView(request):
    return render(request,"survey/admin/admin_dashboard.html")
    
@role_required(allowed_roles=["admin"])
def MangeUsersView(request):
    return render(request,"survey/admin/manage_users.html")

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