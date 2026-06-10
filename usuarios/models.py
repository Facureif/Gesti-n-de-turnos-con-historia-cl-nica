from django.db import models
from django.contrib.auth.models import AbstractUser


class Usuario(AbstractUser):
    ROLES = [
        ('admin', 'Administrador'),
        ('profesional', 'Profesional'),
        ('secretaria', 'Secretaría'),
        ('paciente', 'Paciente'),
    ]
    
    rol = models.CharField(max_length=20, choices=ROLES, default='paciente')
    telefono = models.CharField(max_length=20, blank=True)
    
    def __str__(self):
        return f"{self.get_full_name()} ({self.get_rol_display()})"
    
    class Meta:
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'