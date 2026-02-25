from django.urls import path
from . import views

urlpatterns = [
    path("admin/",views.AdminDashboardView,name="admin_dashboard"),
    path("creator/",views.creatorDashboardView,name="creator_dashboard"),
    path("respondent/",views.respondentDashboardView,name="respondent_dashboard"),
]