from django.urls import path
from . import views_publico

urlpatterns = [
    path('', views_publico.portal_profesional, name='portal_profesional'),
    path('sacar-turno/', views_publico.sacar_turno_profesional, name='sacar_turno_profesional'),
]