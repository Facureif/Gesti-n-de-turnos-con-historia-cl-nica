from django.urls import path
from . import views_publico

urlpatterns = [
    path('', views_publico.portal_consultorio, name='portal_consultorio'),
    path('sacar-turno/<int:profesional_id>/', views_publico.sacar_turno_consultorio, name='sacar_turno_consultorio'),
]
