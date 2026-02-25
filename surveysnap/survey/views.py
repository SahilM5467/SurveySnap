from django.shortcuts import render
from django.contrib.auth.decorators import login_required

# Create your views here.
@login_required(login_url="login") 
def AdminDashboardView(request):
    return render(request,"survey/admin_dashboard.html")

@login_required(login_url="login")
def creatorDashboardView(request):
    return render(request,"survey/creator_dashboard.html")

@login_required(login_url="login")
def respondentDashboardView(request):
    return render(request,"survey/respondent_dashboard.html")