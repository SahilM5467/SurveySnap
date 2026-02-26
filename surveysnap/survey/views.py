from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .decorators import role_required

# Create your views here.

# @login_required(login_url="login") 
@role_required(allowed_roles=["admin"])
def AdminDashboardView(request):
    return render(request,"survey/admin/admin_dashboard.html")

# @login_required(login_url="login")
@role_required(allowed_roles=["creator"])
def creatorDashboardView(request):
    return render(request,"survey/creator/creator_dashboard.html")

# @login_required(login_url="login")
@role_required(allowed_roles=["respondent"])
def respondentDashboardView(request):
    return render(request,"survey/respondent/respondent_dashboard.html")