from django.urls import path
from . import views

urlpatterns = [
    path('nuevo/', views.registrar_paciente, name='registrar_paciente'),
    path('buscar/', views.buscar_paciente, name='buscar_paciente'),
    path('<int:paciente_id>/', views.ficha_paciente, name='ficha_paciente'),
    path('<int:paciente_id>/editar/', views.editar_paciente, name='editar_paciente'),
    path('<int:paciente_id>/ficha-tecnica/', views.ficha_tecnica, name='ficha_tecnica'),
    path('<int:paciente_id>/estudios/', views.estudios_paciente, name='estudios_paciente'),
    path('lesion/agregar/<int:paciente_id>/', views.agregar_lesion, name='agregar_lesion'),
    path('lesion/resuelta/<int:lesion_id>/', views.marcar_lesion_resuelta, name='marcar_lesion_resuelta'),
    path('lesion/eliminar/<int:lesion_id>/', views.eliminar_lesion, name='eliminar_lesion'),
    path('lesion/resuelta/<int:lesion_id>/', views.marcar_lesion_resuelta, name='marcar_lesion_resuelta'),
    path('lesion/eliminar/<int:lesion_id>/', views.eliminar_lesion, name='eliminar_lesion'),
    path('<int:paciente_id>/sesiones/', views.actualizar_sesiones, name='actualizar_sesiones'),
    path('lesion/<int:lesion_id>/seguimiento/', views.seguimiento_lesion, name='seguimiento_lesion'),
    path('lesion/<int:lesion_id>/seguimiento/agregar/', views.agregar_seguimiento, name='agregar_seguimiento'),
    path('lesion/<int:lesion_id>/seguimiento/limpiar/', views.limpiar_seguimientos, name='limpiar_seguimientos'),
    path('seguimiento/<int:seguimiento_id>/eliminar/', views.eliminar_seguimiento, name='eliminar_seguimiento'),
]