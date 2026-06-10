from django.urls import path
from . import views

urlpatterns = [
    # Acciones del panel profesional
    path('confirmar/<int:turno_id>/', views.confirmar_turno, name='confirmar_turno'),
    path('cancelar/<int:turno_id>/', views.cancelar_turno, name='cancelar_turno'),
    path('completar/<int:turno_id>/', views.completar_turno, name='completar_turno'),
    path('no-asistio/<int:turno_id>/', views.no_asistio_turno, name='no_asistio_turno'),
    
    # Formulario público para sacar turno
    path('sacar-turno/', views.sacar_turno_rapido, name='sacar_turno'),
    path('sacar-turno/<int:profesional_id>/', views.sacar_turno_rapido, name='sacar_turno_profesional'),
]