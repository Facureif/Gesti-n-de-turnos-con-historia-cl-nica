from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # Login
    path('login/', auth_views.LoginView.as_view(
        template_name='usuarios/login.html',
        redirect_authenticated_user=True
    ), name='login'),
    
    # Logout
    path('logout/', auth_views.LogoutView.as_view(
        next_page='home'
    ), name='logout'),
    
    # Registro de pacientes (modalidad profesional)
    path('registro/', views.registro_paciente, name='registro'),
]