from django.db import models
from core_app.models import ModeloBase


class Establecimiento(ModeloBase):
    nombre = models.CharField(max_length=200, verbose_name='Nombre')
    direccion = models.CharField(max_length=200, verbose_name='Dirección')
    telefono = models.CharField(max_length=20, verbose_name='Teléfono')
    email = models.EmailField(verbose_name='Email')
    cuit = models.CharField(max_length=13, verbose_name='CUIT')
    logo = models.ImageField(upload_to='logos/', blank=True, verbose_name='Logo')
    
    class Meta:
        verbose_name = 'Establecimiento'
        verbose_name_plural = 'Establecimientos'
    
    def __str__(self):
        return self.nombre


class Sucursal(ModeloBase):
    establecimiento = models.ForeignKey(
        Establecimiento,
        on_delete=models.CASCADE,
        related_name='sucursales',
        verbose_name='Establecimiento'
    )
    nombre = models.CharField(max_length=100, verbose_name='Nombre')
    direccion = models.CharField(max_length=200, verbose_name='Dirección')
    telefono = models.CharField(max_length=20, blank=True, verbose_name='Teléfono')
    
    class Meta:
        verbose_name = 'Sucursal'
        verbose_name_plural = 'Sucursales'
    
    def __str__(self):
        return f"{self.establecimiento} - {self.nombre}"