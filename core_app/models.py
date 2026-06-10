from django.db import models


class ModeloBase(models.Model):
    """Modelo abstracto del que heredan todos los demás"""
    creado = models.DateTimeField(auto_now_add=True, verbose_name='Creado')
    modificado = models.DateTimeField(auto_now=True, verbose_name='Modificado')
    activo = models.BooleanField(default=True, verbose_name='Activo')
    
    class Meta:
        abstract = True


class Persona(ModeloBase):
    """Modelo abstracto para personas (profesionales y pacientes)"""
    nombre = models.CharField(max_length=100, verbose_name='Nombre')
    apellido = models.CharField(max_length=100, verbose_name='Apellido')
    dni = models.CharField(max_length=20, unique=True, verbose_name='DNI')
    fecha_nacimiento = models.DateField(verbose_name='Fecha de Nacimiento')
    telefono = models.CharField(max_length=20, verbose_name='Teléfono')
    email = models.EmailField(blank=True, verbose_name='Email')
    
    class Meta:
        abstract = True
    
    @property
    def nombre_completo(self):
        return f"{self.nombre} {self.apellido}"
    
    def __str__(self):
        return self.nombre_completo