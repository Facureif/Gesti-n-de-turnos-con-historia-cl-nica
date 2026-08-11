from datetime import datetime, timedelta

from django.db import models
from django.db.models import Q
from agendas.models import Agenda, HorarioAtencion
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

    archivo = models.FileField(
    upload_to='turnos/archivos/',
    null=True,
    blank=True,
    verbose_name='Archivo adjunto'
)

    comprobante_pago = models.FileField(
        upload_to='turnos/comprobantes/',
        null=True, blank=True,
        verbose_name='Comprobante de pago'
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
    es_sobreturno = models.BooleanField(
    default=False,
    verbose_name='Sobreturno'
)

    monto_total = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name='Monto Total')
    monto_os = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name='Cubre OS')
    
    monto_coseguro = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Coseguro cobrado'
    )
    os_cobrado = models.BooleanField(default=False, verbose_name='¿Cobrado a la OS?')
    fecha_cobro_os = models.DateField(null=True, blank=True, verbose_name='Fecha de cobro a OS')
    no_asistio_automatico = models.BooleanField(default=False, verbose_name="No asistió por sistema")
    sesion_descontada = models.BooleanField(default=False, verbose_name="Sesión descontada")
    
    google_event_id = models.CharField(max_length=200, blank=True, null=True, verbose_name='ID Evento Google')

    class Meta:
        verbose_name = 'Turno Profesional'
        verbose_name_plural = 'Turnos Profesionales'
        ordering = ['fecha', 'hora_inicio']
    
    def __str__(self):
        return f"{self.fecha} {self.hora_inicio} - {self.paciente.nombre_completo}"

    def save(self, *args, **kwargs):
        # Solo calcular si no es un sobreturno explícito y hay datos básicos
        if not self.es_sobreturno and self.fecha and self.hora_inicio and self.hora_fin:
            agenda = Agenda.objects.filter(
                profesional=self.profesional,
                activo=True,
                fecha_inicio__lte=self.fecha,
            ).filter(
                Q(fecha_fin__isnull=True) | Q(fecha_fin__gte=self.fecha)
            ).first()
            
            if not agenda:
                self.es_sobreturno = True
            else:
                horario = HorarioAtencion.objects.filter(
                    agenda=agenda,
                    dia=self.fecha.weekday()
                ).first()
                
                if not horario:
                    self.es_sobreturno = True
                else:
                    # Verificar que coincida exactamente con algún slot
                    duracion = horario.duracion_turno
                    hora_actual = horario.hora_inicio
                    coincide = False
                    while hora_actual < horario.hora_fin:
                        hora_fin_slot = (datetime.combine(self.fecha, hora_actual) + timedelta(minutes=duracion)).time()
                        if self.hora_inicio == hora_actual and self.hora_fin == hora_fin_slot:
                            coincide = True
                            break
                        hora_actual = hora_fin_slot
                    
                    if not coincide:
                        self.es_sobreturno = True
        
        super().save(*args, **kwargs)
    

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

