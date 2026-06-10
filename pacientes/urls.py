from django.urls import path
from . import views

urlpatterns = [
    path('nuevo/', views.registrar_paciente, name='registrar_paciente'),
    path('buscar/', views.buscar_paciente, name='buscar_paciente'),
    path('<int:paciente_id>/', views.ficha_paciente, name='ficha_paciente'),
    path('<int:paciente_id>/editar/', views.editar_paciente, name='editar_paciente'),

]