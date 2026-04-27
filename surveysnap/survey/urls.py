from django.urls import path

from . import views


urlpatterns = [
    path("admin/admin_dashboard", views.AdminDashboardView, name="admin_dashboard"),
    path("admin/manage_users", views.MangeUsersView, name="manage_users"),
    path("admin/users/add/", views.add_user, name="add_user"),
    path("admin/users/edit/<int:id>/", views.edit_user, name="edit_user"),
    path("admin/users/delete/<int:id>/", views.delete_user, name="delete_user"),
    path("admin/manage_surveys", views.MangeSurveysView, name="manage_surveys"),
    path("admin/manage_templates", views.ManageTemplatesView, name="manage_templates"),
    path("admin/reports", views.ReportsView, name="reports"),
    path("creator/creator_dashboard", views.CreatorDashboardView, name="creator_dashboard"),
    path("creator/create_survey", views.CreateSurveyPageView, name="create_survey_page"),
    path("creator/create_survey/builder/", views.SurveyBuilderView, name="survey_builder"),
    path(
        "creator/create_survey/templates/<slug:template_slug>/preview/",
        views.template_preview,
        name="template_preview",
    ),
    path(
        "creator/create_survey/builder/<int:survey_id>/",
        views.SurveyBuilderView,
        name="survey_builder_edit",
    ),
    path("creator/create_survey/create/", views.create_survey, name="create_survey"),
    path(
        "creator/create_survey/<int:survey_id>/save/",
        views.save_survey,
        name="save_survey",
    ),
    path(
        "creator/create_survey/<int:survey_id>/publish/",
        views.publish_survey,
        name="publish_survey",
    ),
    path(
        "creator/create_survey/<int:survey_id>/unpublish/",
        views.unpublish_survey,
        name="unpublish_survey",
    ),
    path(
        "creator/my_surveys/<int:survey_id>/delete/",
        views.delete_creator_survey,
        name="delete_creator_survey",
    ),
    path(
        "creator/create_survey/<int:survey_id>/preview/",
        views.survey_preview,
        name="survey_preview",
    ),
    path("creator/my_surveys", views.MySurveysView, name="my_surveys"),
    path("creator/analytics", views.AnalyticsView, name="analytics"),
    path("respondent/respondent_dashboard", views.RespondentDashboardView, name="respondent_dashboard"),
    path("respondent/available_surveys", views.AvailableSurveysView, name="available_surveys"),
    path("respondent/my_responses", views.MyResponsesView, name="my_responses"),
    path("respondent/profile", views.ProfileView, name="profile"),
    path("s/<uuid:share_token>/", views.public_survey_detail, name="public_survey_detail"),
]
