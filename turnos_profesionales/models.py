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
    
    class Meta:
        verbose_name = 'Turno Profesional'
        verbose_name_plural = 'Turnos Profesionales'
        ordering = ['fecha', 'hora_inicio']
    
    def __str__(self):
        return f"{self.fecha} {self.hora_inicio} - {self.paciente.nombre_completo}"