
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('',include('core.urls')),
    path('core/',include('core.urls')),
    path('survey/',include('survey.urls'))
]
