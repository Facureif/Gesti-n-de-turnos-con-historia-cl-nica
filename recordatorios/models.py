from django.db import models
from core_app.models import ModeloBase


class PlantillaMensaje(ModeloBase):
    TIPOS = [
        ('confirmacion', 'Confirmación de Turno'),
        ('recordatorio', 'Recordatorio 24hs'),
        ('cancelacion', 'Aviso de Cancelación'),
        ('renovacion', 'Solicitud de Renovación'),
    ]
    
    nombre = models.CharField(max_length=100, verbose_name='Nombre')
    tipo = models.CharField(max_length=30, choices=TIPOS, verbose_name='Tipo')
    contenido = models.TextField(
        verbose_name='Contenido',
        help_text='Variables: {nombre}, {fecha}, {hora}, {profesional}'
    )
    profesional = models.ForeignKey(
        'profesionales.Profesional',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name='Profesional'
    )
    
    class Meta:
        verbose_name = 'Plantilla de Mensaje'
        verbose_name_plural = 'Plantillas de Mensajes'
    
    def __str__(self):
        return f"{self.get_tipo_display()} - {self.nombre}"


class Recordatorio(ModeloBase):
    CANALES = [
        ('whatsapp', 'WhatsApp'),
        ('sms', 'SMS'),
        ('email', 'Email'),
    ]
    
    turno = models.ForeignKey(
        'turnos.Turno',
        on_delete=models.CASCADE,
        verbose_name='Turno'
    )
    canal = models.CharField(max_length=20, choices=CANALES, verbose_name='Canal')
    momento_envio = models.DateTimeField(verbose_name='Momento de Envío')
    enviado = models.BooleanField(default=False, verbose_name='Enviado')
    fecha_envio = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha de Envío'
    )
    confirmado = models.BooleanField(null=True, verbose_name='¿Confirmó?')
    respuesta = models.TextField(blank=True, verbose_name='Respuesta')
    
    class Meta:
        verbose_name = 'Recordatorio'
        verbose_name_plural = 'Recordatorios'
        ordering = ['-momento_envio']
    
    def __str__(self):
        return f"Recordatorio {self.get_canal_display()} - {self.turno}"