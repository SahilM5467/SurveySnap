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
    path('logout/',views.userLogoutView,name='logout'),
]