from django.urls import path
from . import views_portal

urlpatterns = [
    path('panel/', views_portal.panel_paciente, name='panel_paciente'),
    path('mis-turnos/', views_portal.mis_turnos, name='mis_turnos'),
    path('cancelar-turno/<int:turno_id>/', views_portal.cancelar_turno_paciente, name='cancelar_turno_paciente'),
    path('sacar-turno/', views_portal.sacar_turno_paciente, name='sacar_turno_paciente'),
    path('sacar-turno/<int:profesional_id>/', views_portal.sacar_turno_paciente, name='sacar_turno_paciente_profesional'),
    path('editar-mi-ficha/', views_portal.editar_mi_ficha, name='editar_mi_ficha'),
    path('mis-estudios/', views_portal.mis_estudios, name='mis_estudios'),
    path('cambiar-password/', views_portal.cambiar_password, name='cambiar_password'),
]