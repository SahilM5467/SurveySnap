from django.contrib import admin
from django.urls import path,include
from . import views

urlpatterns = [
    path('',views.homeView,name='home'),
    path('features/',views.featuresView,name='features'),
    path('about/',views.aboutView,name='about'),
    path('contact/',views.contactView,name='contact'),
    path('signup/',views.userSignupView,name='signup'),
    path('login/',views.userLoginView,name='login'),
    path('forgot-password/', views.ForgotPasswordView.as_view(), name='password_reset'),
    path('forgot-password/done/', views.ForgotPasswordDoneView.as_view(), name='password_reset_done'),
    path(
        'reset/<uidb64>/<token>/',
        views.ResetPasswordConfirmView.as_view(),
        name='password_reset_confirm'
    ),
    path(
        'reset/complete/',
        views.ResetPasswordCompleteView.as_view(),
        name='password_reset_complete'
    ),
    path('logout/',views.userLogoutView,name='logout'),
    path('logout/auto/',views.userAutoLogoutView,name='auto_logout'),
]
