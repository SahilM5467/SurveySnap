from django.urls import path
from . import views

urlpatterns = [
    path("admin/admin_dashboard",views.AdminDashboardView,name="admin_dashboard"),
    path("admin/manage_users",views.MangeUsersView,name="manage_users"),
    path("admin/manage_surveys",views.MangeSurveysView,name="manage_surveys"),
    path("admin/manage_templates",views.ManageTemplatesView,name="manage_templates"),
    path("admin/reports",views.ReportsView,name="reports"),

    path("creator/creator_dashboard",views.CreatorDashboardView,name="creator_dashboard"),
    path("creator/create_survey",views.CreateSurveyView,name="create_survey"),
    path("creator/my_surveys",views.MySurveysView,name="my_surveys"),
    path("creator/analytics",views.AnalyticsView,name="analytics"),
    
    path("respondent/respondent_dashboard",views.RespondentDashboardView,name="respondent_dashboard"),
    path("respondent/available_surveys",views.AvailableSurveysView,name="available_surveys"),
    path("respondent/my_responses",views.MyResponsesView,name="my_responses"),
    path("respondent/profile",views.ProfileView,name="profile"),
]