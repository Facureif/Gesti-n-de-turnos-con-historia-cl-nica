from django.urls import path
from . import views

urlpatterns = [
    #ejercicio
    path('paciente/<int:paciente_id>/ejercicios/', views.ejercicios_paciente, name='ejercicios_paciente'),
    path('paciente/<int:paciente_id>/ejercicios/agregar/', views.agregar_ejercicio, name='agregar_ejercicio'),
    path('ejercicio/<int:ejercicio_id>/editar/', views.editar_ejercicio, name='editar_ejercicio'),
    path('ejercicio/<int:ejercicio_id>/eliminar/', views.eliminar_ejercicio, name='eliminar_ejercicio'),
    path('ejercicio/imagen/<int:imagen_id>/eliminar/', views.eliminar_imagen_ejercicio, name='eliminar_imagen_ejercicio'),

    #alimentacion
    path('paciente/<int:paciente_id>/planes/', views.planes_alimentacion_paciente, name='planes_alimentacion_paciente'),
    path('paciente/<int:paciente_id>/planes/agregar/', views.agregar_plan_alimentacion, name='agregar_plan_alimentacion'),
    path('plan/<int:plan_id>/editar/', views.editar_plan_alimentacion, name='editar_plan_alimentacion'),
    path('plan/<int:plan_id>/eliminar/', views.eliminar_plan_alimentacion, name='eliminar_plan_alimentacion'),
    path('plan/imagen/<int:imagen_id>/eliminar/', views.eliminar_imagen_plan, name='eliminar_imagen_plan'),
]