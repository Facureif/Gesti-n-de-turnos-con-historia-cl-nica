from django.db import models
from core_app.models import ModeloBase


class TurnoProfesional(ModeloBase):
    """Turnos para consultorios. Requiere paciente registrado."""
    
    ESTADOS = [
        ('pendiente', 'Pendiente'),
        ('confirmado', 'Confirmado'),
        ('cancelado', 'Cancelado'),
        ('no_asistio', 'No Asistió'),
        ('completado', 'Completado'),
        ('en_sala', 'En Sala de Espera'),
    ]
    
    profesional = models.ForeignKey(
        'profesionales.Profesional',
        on_delete=models.CASCADE,
        verbose_name='Profesional'
    )
    paciente = models.ForeignKey(
        'pacientes.Paciente',
        on_delete=models.CASCADE,
        verbose_name='Paciente'
    )
    fecha = models.DateField(verbose_name='Fecha')
    hora_inicio = models.TimeField(verbose_name='Hora de Inicio')
    hora_fin = models.TimeField(verbose_name='Hora de Fin')
    estado = models.CharField(
        max_length=20,
        choices=ESTADOS,
        default='pendiente',
        verbose_name='Estado'
    )
    
    # Info de la consulta
    tipo_consulta = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Tipo de Consulta'
    )
    notas_internas = models.TextField(
        blank=True,
        verbose_name='Notas Internas'
    )
    
    # Obra social
    obra_social = models.ForeignKey(
        'obras_sociales.ObraSocial',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Obra Social'
    )
    requiere_autorizacion = models.BooleanField(
        default=False,
        verbose_name='Requiere Autorización'
    )
    
    enviar_recordatorio = models.BooleanField(
        default=True,
        verbose_name='Enviar Recordatorio'
    )
    establecimiento = models.ForeignKey(
    'establecimientos.Establecimiento',
    on_delete=models.SET_NULL,
    null=True,
    blank=True,
    verbose_name='Consultorio'
)

    class Meta:
        verbose_name = 'Turno Profesional'
        verbose_name_plural = 'Turnos Profesionales'
        ordering = ['fecha', 'hora_inicio']
    
    def __str__(self):
        return f"{self.fecha} {self.hora_inicio} - {self.paciente.nombre_completo}"
    

class ArchivoTurno(ModeloBase):
    """Imágenes/archivos adjuntos a un turno (recetas, derivaciones, etc.)."""
    turno = models.ForeignKey(
        TurnoProfesional,
        on_delete=models.CASCADE,
        related_name='archivos',
        verbose_name='Turno'
    )
    archivo = models.FileField(
        upload_to='turnos/%Y/%m/',
        verbose_name='Archivo'
    )
    descripcion = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Descripción'
    )
    
    class Meta:
        verbose_name = 'Archivo de Turno'
        verbose_name_plural = 'Archivos de Turnos'
    
    def __str__(self):
        return f"Archivo {self.id} - Turno {self.turno.id}"
    
    @property
    def es_imagen(self):
        ext = self.archivo.name.split('.')[-1].lower()
        return ext in ['jpg', 'jpeg', 'png', 'gif', 'webp']    