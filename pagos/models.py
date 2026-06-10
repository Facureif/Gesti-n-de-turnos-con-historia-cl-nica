from django.db import models
from core_app.models import ModeloBase


class Pago(ModeloBase):
    METODOS_PAGO = [
        ('efectivo', 'Efectivo'),
        ('tarjeta_debito', 'Tarjeta de Débito'),
        ('tarjeta_credito', 'Tarjeta de Crédito'),
        ('transferencia', 'Transferencia'),
        ('mercado_pago', 'Mercado Pago'),
        ('obra_social', 'Obra Social'),
    ]
    
    ESTADOS = [
        ('pendiente', 'Pendiente'),
        ('pagado', 'Pagado'),
        ('parcial', 'Pago Parcial'),
        ('cancelado', 'Cancelado'),
    ]
    
    turno = models.OneToOneField(
        'turnos.Turno',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Turno'
    )
    paciente = models.ForeignKey(
        'pacientes.Paciente',
        on_delete=models.CASCADE,
        verbose_name='Paciente'
    )
    monto_total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name='Monto Total'
    )
    metodo_pago = models.CharField(
        max_length=20,
        choices=METODOS_PAGO,
        default='efectivo',
        verbose_name='Método de Pago'
    )
    estado = models.CharField(
        max_length=20,
        choices=ESTADOS,
        default='pendiente',
        verbose_name='Estado'
    )
    fecha_pago = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha de Pago'
    )
    comprobante = models.FileField(
        upload_to='comprobantes/',
        blank=True,
        verbose_name='Comprobante'
    )
    notas = models.TextField(blank=True, verbose_name='Notas')
    
    class Meta:
        verbose_name = 'Pago'
        verbose_name_plural = 'Pagos'
        ordering = ['-creado']
    
    def __str__(self):
        return f"Pago #{self.id} - {self.paciente} - ${self.monto_total}"