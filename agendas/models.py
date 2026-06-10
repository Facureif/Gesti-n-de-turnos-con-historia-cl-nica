from django.db import models
from core_app.models import ModeloBase


class Agenda(ModeloBase):
    """Configuración de disponibilidad de un profesional"""
    profesional = models.ForeignKey(
        'profesionales.Profesional',
        on_delete=models.CASCADE,
        verbose_name='Profesional'
    )
    fecha_inicio = models.DateField(verbose_name='Fecha de Inicio')
    fecha_fin = models.DateField(
        null=True,
        blank=True,
        verbose_name='Fecha de Fin'
    )
    acepta_sobreturnos = models.BooleanField(
        default=False,
        verbose_name='Acepta Sobreturnos'
    )
    tiempo_entre_turnos = models.IntegerField(
        default=0,
        verbose_name='Minutos entre turnos'
    )
    
    class Meta:
        verbose_name = 'Agenda'
        verbose_name_plural = 'Agendas'
    
    def __str__(self):
        return f"Agenda de {self.profesional}"


class HorarioAtencion(ModeloBase):
    """Bloques horarios para cada día de la semana"""
    DIAS = [
        (0, 'Lunes'),
        (1, 'Martes'),
        (2, 'Miércoles'),
        (3, 'Jueves'),
        (4, 'Viernes'),
        (5, 'Sábado'),
        (6, 'Domingo'),
    ]
    
    agenda = models.ForeignKey(
        Agenda,
        on_delete=models.CASCADE,
        related_name='horarios',
        verbose_name='Agenda'
    )
    dia = models.IntegerField(choices=DIAS, verbose_name='Día')
    hora_inicio = models.TimeField(verbose_name='Hora de Inicio')
    hora_fin = models.TimeField(verbose_name='Hora de Fin')
    duracion_turno = models.IntegerField(
        verbose_name='Duración del turno (minutos)'
    )
    
    class Meta:
        verbose_name = 'Horario de Atención'
        verbose_name_plural = 'Horarios de Atención'
        ordering = ['dia', 'hora_inicio']
    
    def __str__(self):
        return f"{self.get_dia_display()} {self.hora_inicio} - {self.hora_fin}"


class BloqueoAgenda(ModeloBase):
    """Feriados, vacaciones o bloqueos temporales"""
    agenda = models.ForeignKey(
        Agenda,
        on_delete=models.CASCADE,
        verbose_name='Agenda'
    )
    fecha = models.DateField(verbose_name='Fecha')
    hora_inicio = models.TimeField(
        null=True,
        blank=True,
        verbose_name='Hora de Inicio'
    )
    hora_fin = models.TimeField(
        null=True,
        blank=True,
        verbose_name='Hora de Fin'
    )
    motivo = models.CharField(max_length=200, verbose_name='Motivo')
    
    class Meta:
        verbose_name = 'Bloqueo de Agenda'
        verbose_name_plural = 'Bloqueos de Agenda'
    
    def __str__(self):
        return f"Bloqueo: {self.fecha} - {self.motivo}"