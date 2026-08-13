from django.urls import path
from . import views

urlpatterns = [
    path('paciente/<int:paciente_id>/ejercicios/', views.ejercicios_paciente, name='ejercicios_paciente'),
    path('paciente/<int:paciente_id>/ejercicios/agregar/', views.agregar_ejercicio, name='agregar_ejercicio'),
    path('ejercicio/<int:ejercicio_id>/editar/', views.editar_ejercicio, name='editar_ejercicio'),
    path('ejercicio/<int:ejercicio_id>/eliminar/', views.eliminar_ejercicio, name='eliminar_ejercicio'),
    path('ejercicio/imagen/<int:imagen_id>/eliminar/', views.eliminar_imagen_ejercicio, name='eliminar_imagen_ejercicio'),
]