from django.urls import include, path
from . import views_cliente

urlpatterns = [
    path('', views_cliente.portal, name='portal_cliente'),
    path('profesional/<int:profesional_id>/', views_cliente.sacar_turno, name='sacar_turno_cliente'),
    path('api/horarios-disponibles/<int:establecimiento_id>/', views_cliente.api_horarios_disponibles, name='api_horarios_disponibles'),
]