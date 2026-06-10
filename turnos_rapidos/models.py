from django.db import models
from core_app.models import ModeloBase


class TurnoRapido(ModeloBase):
    """Turnos para peluquerías, barberías, etc. Sin paciente registrado."""
    
    ESTADOS = [
        ('pendiente', 'Pendiente'),
        ('confirmado', 'Confirmado'),
        ('cancelado', 'Cancelado'),
        ('no_asistio', 'No Asistió'),
        ('completado', 'Completado'),
    ]
    
    profesional = models.ForeignKey(
        'profesionales.Profesional',
        on_delete=models.CASCADE,
        verbose_name='Profesional'
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
    
    # Datos del cliente (sin registro)
    nombre_cliente = models.CharField(max_length=100, verbose_name='Nombre del Cliente')
    telefono_cliente = models.CharField(max_length=20, verbose_name='Teléfono')
    nota = models.TextField(blank=True, verbose_name='Nota')
    
    enviar_recordatorio = models.BooleanField(
        default=True,
        verbose_name='Enviar Recordatorio'
    )
    
    class Meta:
        verbose_name = 'Turno Rápido'
        verbose_name_plural = 'Turnos Rápidos'
        ordering = ['fecha', 'hora_inicio']
    
    def __str__(self):
        return f"{self.fecha} {self.hora_inicio} - {self.nombre_cliente}"