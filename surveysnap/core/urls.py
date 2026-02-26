from django.contrib import admin
from django.urls import path,include
from . import views

urlpatterns = [
    path('',views.homeView,name='home'),
    path('signup/',views.userSignupView,name='signup'),
    path('login/',views.userLoginView,name='login'),
    path('logout/',views.userLogoutView,name='logout'),
]