from django.urls import path
from . import views

urlpatterns = [
    path('panel/', views.panel_profesional, name='panel_profesional'),
    path('confirmar/<int:turno_id>/', views.confirmar_turno, name='confirmar_turno_pro'),
    path('cancelar/<int:turno_id>/', views.cancelar_turno, name='cancelar_turno_pro'),
    path('completar/<int:turno_id>/', views.completar_turno, name='completar_turno_pro'),
    path('no-asistio/<int:turno_id>/', views.no_asistio_turno, name='no_asistio_pro'),
    path('editar/<int:turno_id>/', views.editar_turno, name='editar_turno_pro'),  
    path('asignar/<int:paciente_id>/', views.asignar_turno, name='asignar_turno'),
    path('evolucion/<int:turno_id>/', views.cargar_evolucion, name='cargar_evolucion'),
    path('calendario/', views.calendario_semanal, name='calendario_semanal'),
    path('asignar-desde-calendario/', views.asignar_turno_calendario, name='asignar_turno_calendario'),
    path('bloquear-dia/', views.bloquear_dia, name='bloquear_dia'),
    path('desbloquear/<int:bloqueo_id>/', views.desbloquear_dia, name='desbloquear_dia'),
]