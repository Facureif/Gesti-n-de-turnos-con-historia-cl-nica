from django.db import models
from core_app.models import Persona


class Profesional(Persona):
    ESPECIALIDADES = [
        ('odontologia', 'Odontología'),
        ('kinesiologia', 'Kinesiología'),
        ('psicologia', 'Psicología'),
        ('medicina_general', 'Medicina General'),
        ('dermatologia', 'Dermatología'),
        ('estetica', 'Estética'),
        ('veterinaria', 'Veterinaria'),
        ('otro', 'Otro'),
    ]
    
    usuario = models.OneToOneField(
        'usuarios.Usuario',
        on_delete=models.CASCADE,
        verbose_name='Usuario'
    )
    especialidad = models.CharField(
        max_length=50,
        choices=ESPECIALIDADES,
        verbose_name='Especialidad'
    )
    matricula = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='Matrícula Profesional'
    )
    color_calendario = models.CharField(
        max_length=7,
        default='#4A90D9',
        verbose_name='Color en Calendario'
    )
    acepta_obra_social = models.BooleanField(
        default=False,
        verbose_name='Acepta Obra Social'
    )
    descripcion = models.TextField(
        blank=True,
        verbose_name='Descripción Profesional'
    )
    
    foto = models.ImageField(
    upload_to='profesionales/',
    blank=True,
    null=True,
    verbose_name='Foto de Perfil'
    )
    establecimientos = models.ManyToManyField(
    'establecimientos.Establecimiento',
    blank=True,
    related_name='profesionales',
    verbose_name='Consultorios donde atiende'
    )

    class Meta:
        verbose_name = 'Profesional'
        verbose_name_plural = 'Profesionales'
        ordering = ['apellido', 'nombre']
    
    def __str__(self):
        return f"{self.nombre_completo} - {self.get_especialidad_display()}"