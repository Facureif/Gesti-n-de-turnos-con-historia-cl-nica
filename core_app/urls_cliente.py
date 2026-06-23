from django.urls import path
from . import views_cliente

urlpatterns = [
    path('', views_cliente.portal, name='portal_cliente'),
    path('profesional/<int:profesional_id>/', views_cliente.sacar_turno, name='sacar_turno_cliente'),
]