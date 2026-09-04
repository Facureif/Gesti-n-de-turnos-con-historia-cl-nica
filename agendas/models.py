# agendas/models.py
from django.db import models
from django.core.exceptions import ValidationError
from core_app.models import ModeloBase



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
    precio_particular = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name='Precio consulta particular (en este consultorio)'
    )
    # Obras sociales y planes específicos de este consultorio
    obras_sociales = models.ManyToManyField(
        'obras_sociales.ObraSocial',
        blank=True,
        related_name='agendas',
        verbose_name='Obras Sociales (en este consultorio)'
    )
    planes = models.ManyToManyField(
        'obras_sociales.Plan',
        blank=True,
        related_name='agendas',
        verbose_name='Planes (en este consultorio)'
    )
    # Contacto específico para este consultorio (puede diferir del global)
    email_contacto = models.EmailField(
        blank=True, null=True,
        verbose_name='Email de contacto (en este consultorio)'
    )
    telefono_contacto = models.CharField(
        max_length=20, blank=True, null=True,
        verbose_name='Teléfono de contacto (en este consultorio)'
    )
    establecimiento = models.ForeignKey(
        'establecimientos.Establecimiento',
        on_delete=models.CASCADE,
        null=False,
        blank=False,
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

    def horarios_agrupados(self):
        """
        Devuelve una lista de strings con los horarios agrupados por días consecutivos
        que comparten el mismo horario de inicio y fin.
        Ejemplo: ['Lunes a Viernes: 09:00 - 18:00', 'Sábado: 09:00 - 12:00']
        """
        # Obtener horarios ordenados por día
        horarios = list(self.horarios.order_by('dia'))
        if not horarios:
            return []

        # Mapeo de los días para mostrarlos
        # Ajustá según tu modelo. Si usás choices, podés usar get_dia_display.
        from collections import OrderedDict
        dias_semana = {0: 'Lunes', 1: 'Martes', 2: 'Miércoles', 3: 'Jueves', 4: 'Viernes', 5: 'Sábado', 6: 'Domingo'}

        # Agrupar
        grupos = []
        grupo_actual = [horarios[0]]

        for actual, siguiente in zip(horarios, horarios[1:]):
            mismo_horario = (actual.hora_inicio == siguiente.hora_inicio and 
                             actual.hora_fin == siguiente.hora_fin)
            dia_consecutivo = (siguiente.dia - actual.dia == 1)

            if mismo_horario and dia_consecutivo:
                grupo_actual.append(siguiente)
            else:
                grupos.append(grupo_actual)
                grupo_actual = [siguiente]
        grupos.append(grupo_actual)  # último grupo

        # Formatear cada grupo
        resultado = []
        for grupo in grupos:
            if len(grupo) == 1:
                dia = dias_semana.get(grupo[0].dia, str(grupo[0].dia))
                resultado.append(f"{dia}: {grupo[0].hora_inicio.strftime('%H:%M')} - {grupo[0].hora_fin.strftime('%H:%M')}")
            else:
                dia_inicio = dias_semana.get(grupo[0].dia, str(grupo[0].dia))
                dia_fin = dias_semana.get(grupo[-1].dia, str(grupo[-1].dia))
                resultado.append(f"{dia_inicio} a {dia_fin}: {grupo[0].hora_inicio.strftime('%H:%M')} - {grupo[0].hora_fin.strftime('%H:%M')}")

        return resultado

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