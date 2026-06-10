from django.urls import path
from . import views

urlpatterns = [
    path('perfil/', views.mi_perfil, name='mi_perfil'),
]