from django.db import models
from core_app.models import ModeloBase


class ObraSocial(ModeloBase):
    """Obras sociales (OSDE, IOMA, PAMI, etc.)"""
    nombre = models.CharField(max_length=200, verbose_name='Nombre')
    sigla = models.CharField(max_length=20, verbose_name='Sigla')
    telefono = models.CharField(max_length=20, blank=True, verbose_name='Teléfono')
    email = models.EmailField(blank=True, verbose_name='Email')
    activo = models.BooleanField(default=True, verbose_name='Activo')
    
    class Meta:
        verbose_name = 'Obra Social'
        verbose_name_plural = 'Obras Sociales'
        ordering = ['nombre']
    
    def __str__(self):
        return f"{self.nombre} ({self.sigla})"


class Plan(ModeloBase):
    """Planes de cada obra social (OSDE 210, OSDE 310, etc.)"""
    obra_social = models.ForeignKey(
        ObraSocial,
        on_delete=models.CASCADE,
        related_name='planes',
        verbose_name='Obra Social'
    )
    nombre = models.CharField(max_length=100, verbose_name='Nombre del Plan')
    requiere_autorizacion = models.BooleanField(
        default=False,
        verbose_name='Requiere Autorización'
    )
    coseguro_fijo = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name='Coseguro Fijo'
    )
    coseguro_porcentaje = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        verbose_name='Coseguro (%)'
    )
    
    class Meta:
        verbose_name = 'Plan'
        verbose_name_plural = 'Planes'
        ordering = ['obra_social', 'nombre']
    
    def __str__(self):
        return f"{self.obra_social.sigla} - {self.nombre}"