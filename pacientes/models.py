from django.db import models
from core_app.models import Persona


class Paciente(Persona):
    GENEROS = [
        ('M', 'Masculino'),
        ('F', 'Femenino'),
        ('X', 'No binario'),
    ]
    
    usuario = models.OneToOneField(
        'usuarios.Usuario',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Usuario'
    )
    genero = models.CharField(
        max_length=1,
        choices=GENEROS,
        blank=True,
        verbose_name='Género'
    )
    direccion = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Dirección'
    )
    obra_social = models.ForeignKey(
        'obras_sociales.ObraSocial',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Obra Social'
    )
    numero_afiliado = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='Número de Afiliado'
    )
    plan_obra_social = models.ForeignKey(
        'obras_sociales.Plan',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Plan'
    )
    observaciones = models.TextField(
        blank=True,
        verbose_name='Observaciones'
    )
    sesiones_autorizadas = models.IntegerField(
    null=True,
    blank=True,
    verbose_name='Sesiones Autorizadas'
    )
    sesiones_restantes = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='Sesiones Restantes'
    )
    fecha_vencimiento_sesiones = models.DateField(
        null=True,
        blank=True,
        verbose_name='Vencimiento de Sesiones'
    )

    # Contacto de emergencia
    contacto_emergencia_nombre = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Contacto Emergencia - Nombre'
    )
    contacto_emergencia_telefono = models.CharField(
        max_length=20,
        blank=True,
        verbose_name='Contacto Emergencia - Teléfono'
    )
    
    class Meta:
        verbose_name = 'Paciente'
        verbose_name_plural = 'Pacientes'
        ordering = ['apellido', 'nombre']
    
    def __str__(self):
        return self.nombre_completo
    

class PacienteObraSocial(models.Model):
    """Obras sociales del paciente (puede tener varias)."""
    paciente = models.ForeignKey(
        Paciente,
        on_delete=models.CASCADE,
        related_name='mis_obras_sociales'
    )
    obra_social = models.ForeignKey(
        'obras_sociales.ObraSocial',
        on_delete=models.CASCADE,
        verbose_name='Obra Social'
    )
    plan = models.ForeignKey(
        'obras_sociales.Plan',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Plan'
    )
    numero_afiliado = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='Número de Afiliado'
    )
    activa = models.BooleanField(
        default=True,
        verbose_name='Activa'
    )
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Obra Social del Paciente'
        verbose_name_plural = 'Obras Sociales del Paciente'
        ordering = ['-activa', 'obra_social__nombre']
        unique_together = ['paciente', 'obra_social', 'plan']  # Evita duplicados
    
    def __str__(self):
        plan_str = f" - {self.plan.nombre}" if self.plan else ""
        return f"{self.obra_social.nombre}{plan_str} ({'Activa' if self.activa else 'Inactiva'})"    