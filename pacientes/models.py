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
    genero = models.CharField(max_length=1, choices=GENEROS, blank=True, verbose_name='Género')
    direccion = models.CharField(max_length=200, blank=True, verbose_name='Dirección')
    obra_social = models.ForeignKey(
        'obras_sociales.ObraSocial',
        on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name='Obra Social'
    )
    numero_afiliado = models.CharField(max_length=50, blank=True, verbose_name='Número de Afiliado')
    plan_obra_social = models.ForeignKey(
        'obras_sociales.Plan',
        on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name='Plan'
    )
    observaciones = models.TextField(blank=True, verbose_name='Observaciones')

    # ❌ ESTOS CAMPOS SE VAN
    # sesiones_autorizadas
    # sesiones_restantes
    # fecha_vencimiento_sesiones

    contacto_emergencia_nombre = models.CharField(max_length=100, blank=True)
    contacto_emergencia_telefono = models.CharField(max_length=20, blank=True)
    
    class Meta:
        verbose_name = 'Paciente'
        verbose_name_plural = 'Pacientes'
        ordering = ['apellido', 'nombre']
    
    def __str__(self):
        return self.nombre_completo


class PacienteObraSocial(models.Model):
    """Cada obra social del paciente con sus propias sesiones."""
    paciente = models.ForeignKey(
        Paciente, on_delete=models.CASCADE, related_name='mis_obras_sociales'
    )
    obra_social = models.ForeignKey(
        'obras_sociales.ObraSocial', on_delete=models.CASCADE, verbose_name='Obra Social'
    )
    plan = models.ForeignKey(
        'obras_sociales.Plan', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Plan'
    )
    numero_afiliado = models.CharField(max_length=50, blank=True, verbose_name='Número de Afiliado')
    profesional = models.ForeignKey(
        'profesionales.Profesional',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Profesional que autoriza'
    )
    
    # ✅ AHORA LAS SESIONES VAN ACÁ
    sesiones_autorizadas = models.IntegerField(null=True, blank=True, verbose_name='Sesiones Autorizadas')
    sesiones_restantes = models.IntegerField(null=True, blank=True, verbose_name='Sesiones Restantes')
    fecha_vencimiento = models.DateField(null=True, blank=True, verbose_name='Vencimiento')
    
    activa = models.BooleanField(default=True, verbose_name='Activa')
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Obra Social del Paciente'
        verbose_name_plural = 'Obras Sociales del Paciente'
        ordering = ['-activa', 'obra_social__nombre']
        unique_together = ['paciente', 'obra_social', 'plan', 'profesional']
    
    def __str__(self):
        plan_str = f" - {self.plan.nombre}" if self.plan else ""
        return f"{self.obra_social.nombre}{plan_str} ({'Activa' if self.activa else 'Inactiva'})"
    
    def get_sesiones_para_profesional(self, profesional):
        """Devuelve la primera OS activa con sesiones para un profesional específico."""
        return self.mis_obras_sociales.filter(
            profesional=profesional,
            activa=True,
            sesiones_restantes__isnull=False
        ).first()


class EstudioMedico(models.Model):
    """Estudios complementarios subidos por el profesional."""
    paciente = models.ForeignKey(
        'pacientes.Paciente', on_delete=models.CASCADE, related_name='estudios_medicos'
    )
    profesional = models.ForeignKey(
        'profesionales.Profesional', on_delete=models.SET_NULL, null=True, related_name='estudios_subidos'
    )
    evolucion = models.ForeignKey(
        'historias_clinicas.Evolucion', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='estudios_complementarios'
    )
    titulo = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True)
    archivo = models.FileField(upload_to='estudios/%Y/%m/')
    tipo_estudio = models.CharField(
        max_length=50,
        choices=[
            ('radiografia', 'Radiografía'),
            ('laboratorio', 'Análisis de Laboratorio'),
            ('tomografia', 'Tomografía'),
            ('resonancia', 'Resonancia Magnética'),
            ('ecografia', 'Ecografía'),
            ('otro', 'Otro'),
        ],
        default='otro'
    )
    fecha_estudio = models.DateField(null=True, blank=True)
    creado = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-creado']
        verbose_name = 'Estudio Médico'
        verbose_name_plural = 'Estudios Médicos'
    
    def __str__(self):
        return f"{self.titulo} - {self.paciente.nombre_completo}"