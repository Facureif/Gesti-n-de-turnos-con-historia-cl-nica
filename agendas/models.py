# agendas/models.py
from django.db import models
from django.core.exceptions import ValidationError
from core_app.models import ModeloBase


# agendas/models.py
class Agenda(ModeloBase):
    profesional = models.ForeignKey(
        'profesionales.Profesional',
        on_delete=models.CASCADE,
        verbose_name='Profesional'
    )
    fecha_inicio = models.DateField(verbose_name='Fecha de Inicio')
    fecha_fin = models.DateField(null=True, blank=True, verbose_name='Fecha de Fin')
    acepta_sobreturnos = models.BooleanField(default=False, verbose_name='Acepta Sobreturnos')
    tiempo_entre_turnos = models.IntegerField(default=0, verbose_name='Minutos entre turnos')
    
    establecimiento = models.ForeignKey(
        'establecimientos.Establecimiento',
        on_delete=models.CASCADE,
        null=False,  # ← Cambiá a False (obligatorio)
        blank=False,  # ← Cambiá a False (obligatorio)
        verbose_name='Consultorio'
    )
    
    pacientes_simultaneos = models.IntegerField(
        default=1,
        verbose_name='Pacientes simultáneos',
        help_text='Cantidad máxima de pacientes que puede atender al mismo tiempo'
    )

    class Meta:
        verbose_name = 'Agenda'
        verbose_name_plural = 'Agendas'
        unique_together = ['profesional', 'establecimiento']

    def __str__(self):
        est = self.establecimiento.nombre if self.establecimiento else "Sin consultorio"
        return f"{self.profesional} - {est}"

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
        est = self.agenda.establecimiento.nombre if self.agenda.establecimiento else ""
        return f"{self.get_dia_display()} {self.hora_inicio.strftime('%H:%M')}-{self.hora_fin.strftime('%H:%M')} ({est})"

    def clean(self):
        """Validar que no se solape con otros horarios del mismo profesional"""
        from datetime import datetime, timedelta
        
        if self.hora_inicio >= self.hora_fin:
            raise ValidationError('La hora de inicio debe ser anterior a la hora de fin.')
        
        # Buscar otros horarios del mismo profesional en otras agendas
        otros_horarios = HorarioAtencion.objects.filter(
            agenda__profesional=self.agenda.profesional,
            dia=self.dia
        ).exclude(
            id=self.id
        ).select_related('agenda__establecimiento')
        
        for otro in otros_horarios:
            # Verificar solapamiento
            if (self.hora_inicio < otro.hora_fin and self.hora_fin > otro.hora_inicio):
                otro_est = otro.agenda.establecimiento.nombre if otro.agenda.establecimiento else "Sin consultorio"
                raise ValidationError(
                    f'Se solapa con horario del {self.get_dia_display()} '
                    f'{otro.hora_inicio.strftime("%H:%M")}-{otro.hora_fin.strftime("%H:%M")} '
                    f'en {otro_est}'
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


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
        est = self.agenda.establecimiento.nombre if self.agenda.establecimiento else ""
        return f"Bloqueo: {self.fecha} - {self.motivo} ({est})"