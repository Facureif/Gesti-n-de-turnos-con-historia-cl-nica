from django.contrib import admin
from .models import Pago


@admin.register(Pago)
class PagoAdmin(admin.ModelAdmin):
    list_display = ('id', 'paciente', 'turno_info', 'monto_total', 
                    'metodo_pago', 'estado', 'fecha_pago')
    list_filter = ('metodo_pago', 'estado', 'fecha_pago')
    search_fields = ('paciente__nombre', 'paciente__apellido', 'id')
    date_hierarchy = 'fecha_pago'
    readonly_fields = ('creado', 'modificado')
    
    fieldsets = (
        (None, {
            'fields': ('turno', 'paciente', 'monto_total', 'metodo_pago')
        }),
        ('Estado del Pago', {
            'fields': ('estado', 'fecha_pago', 'comprobante')
        }),
        ('Información Adicional', {
            'fields': ('notas', 'activo')
        }),
    )
    
    def turno_info(self, obj):
        if obj.turno:
            return f"{obj.turno.fecha} {obj.turno.hora_inicio}"
        return "—"
    turno_info.short_description = 'Turno'