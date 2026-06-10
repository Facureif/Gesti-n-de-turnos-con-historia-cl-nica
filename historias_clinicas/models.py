from django.db import models
from core_app.models import ModeloBase


class HistoriaClinica(ModeloBase):
    paciente = models.OneToOneField(
        'pacientes.Paciente',
        on_delete=models.CASCADE,
        verbose_name='Paciente'
    )
    numero_historia = models.CharField(
        max_length=20,
        unique=True,
        verbose_name='Número de Historia'
    )
    antecedentes_personales = models.TextField(
        blank=True,
        verbose_name='Antecedentes Personales'
    )
    antecedentes_familiares = models.TextField(
        blank=True,
        verbose_name='Antecedentes Familiares'
    )
    alergias = models.TextField(blank=True, verbose_name='Alergias')
    medicacion_habitual = models.TextField(
        blank=True,
        verbose_name='Medicación Habitual'
    )
    
    class Meta:
        verbose_name = 'Historia Clínica'
        verbose_name_plural = 'Historias Clínicas'
    
    def __str__(self):
        return f"HC #{self.numero_historia} - {self.paciente}"


class Evolucion(ModeloBase):
    historia_clinica = models.ForeignKey(
        HistoriaClinica,
        on_delete=models.CASCADE,
        related_name='evoluciones',
        verbose_name='Historia Clínica'
    )
    turno = models.OneToOneField(
        'turnos.Turno',
        on_delete=models.CASCADE,
        verbose_name='Turno'
    )
    profesional = models.ForeignKey(
        'profesionales.Profesional',
        on_delete=models.CASCADE,
        verbose_name='Profesional'
    )
    motivo_consulta = models.TextField(verbose_name='Motivo de Consulta')
    diagnostico = models.TextField(blank=True, verbose_name='Diagnóstico')
    tratamiento_realizado = models.TextField(
        blank=True,
        verbose_name='Tratamiento Realizado'
    )
    indicaciones = models.TextField(blank=True, verbose_name='Indicaciones')
    proximo_control = models.DateField(
        null=True,
        blank=True,
        verbose_name='Próximo Control'
    )
    
    class Meta:
        verbose_name = 'Evolución'
        verbose_name_plural = 'Evoluciones'
        ordering = ['-creado']
    
    def __str__(self):
        return f"Evolución {self.creado.date()} - {self.paciente}"


class ArchivoClinico(ModeloBase):
    TIPOS = [
        ('rx', 'Radiografía'),
        ('foto', 'Fotografía'),
        ('estudio', 'Estudio'),
        ('receta', 'Receta'),
        ('otro', 'Otro'),
    ]
    
    evolucion = models.ForeignKey(
        Evolucion,
        on_delete=models.CASCADE,
        related_name='archivos',
        verbose_name='Evolución'
    )
    archivo = models.FileField(upload_to='hc/%Y/%m/', verbose_name='Archivo')
    descripcion = models.CharField(max_length=200, verbose_name='Descripción')
    tipo = models.CharField(max_length=20, choices=TIPOS, verbose_name='Tipo')
    
    class Meta:
        verbose_name = 'Archivo Clínico'
        verbose_name_plural = 'Archivos Clínicos'
    
    def __str__(self):
        return f"{self.get_tipo_display()} - {self.descripcion}"