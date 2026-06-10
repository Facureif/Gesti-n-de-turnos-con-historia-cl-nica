from django.urls import path
from . import views

urlpatterns = [
    # Panel del profesional (vista rápida)
    path('panel/', views.panel_rapido, name='panel_rapido'),
    
    # Acciones
    path('confirmar/<int:turno_id>/', views.confirmar_turno_rapido, name='confirmar_turno_rapido'),
    path('cancelar/<int:turno_id>/', views.cancelar_turno_rapido, name='cancelar_turno_rapido'),
    path('completar/<int:turno_id>/', views.completar_turno_rapido, name='completar_turno_rapido'),
    path('no-asistio/<int:turno_id>/', views.no_asistio_turno_rapido, name='no_asistio_rapido'),
    
    # Formulario público
    path('sacar-turno/', views.sacar_turno_rapido, name='sacar_turno_rapido'),
    path('sacar-turno/<int:profesional_id>/', views.sacar_turno_rapido, name='sacar_turno_rapido_profesional'),
]