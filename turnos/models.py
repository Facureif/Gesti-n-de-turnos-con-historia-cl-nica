from django.db import models
from core_app.models import ModeloBase


class Turno(ModeloBase):
    ESTADOS = [
        ('disponible', 'Disponible'),
        ('pendiente', 'Pendiente de Confirmación'),
        ('confirmado', 'Confirmado'),
        ('cancelado', 'Cancelado'),
        ('no_asistio', 'No Asistió'),
        ('completado', 'Completado'),
        ('bloqueado', 'Bloqueado'),
    ]
    
    profesional = models.ForeignKey(
        'profesionales.Profesional',
        on_delete=models.CASCADE,
        verbose_name='Profesional'
    )
    paciente = models.ForeignKey(
        'pacientes.Paciente',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Paciente'
    )
    fecha = models.DateField(verbose_name='Fecha')
    hora_inicio = models.TimeField(verbose_name='Hora de Inicio')
    hora_fin = models.TimeField(verbose_name='Hora de Fin')
    estado = models.CharField(
        max_length=20,
        choices=ESTADOS,
        default='disponible',
        verbose_name='Estado'
    )
    
    # Para modalidad rápida (sin paciente registrado)
    nombre_no_registrado = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Nombre (no registrado)'
    )
    telefono_no_registrado = models.CharField(
        max_length=20,
        blank=True,
        verbose_name='Teléfono (no registrado)'
    )
    
    # Info adicional
    motivo_consulta = models.TextField(
        blank=True,
        verbose_name='Motivo de Consulta'
    )
    notas_internas = models.TextField(
        blank=True,
        verbose_name='Notas Internas'
    )
    enviar_recordatorio = models.BooleanField(
        default=True,
        verbose_name='Enviar Recordatorio'
    )
    
    class Meta:
        verbose_name = 'Turno'
        verbose_name_plural = 'Turnos'
        ordering = ['fecha', 'hora_inicio']
        constraints = [
            models.UniqueConstraint(
                fields=['profesional', 'fecha', 'hora_inicio'],
                name='unico_turno_profesional'
            )
        ]
    
    def __str__(self):
        paciente_nombre = self.paciente.nombre_completo if self.paciente else self.nombre_no_registrado or 'Disponible'
        return f"{self.fecha} {self.hora_inicio} - {paciente_nombre}"