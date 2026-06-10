from django.contrib import admin
from .models import TurnoRapido


@admin.register(TurnoRapido)
class TurnoRapidoAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'hora_inicio', 'profesional', 'nombre_cliente', 
                    'telefono_cliente', 'estado')
    list_filter = ('estado', 'profesional', 'fecha')
    search_fields = ('nombre_cliente', 'telefono_cliente', 'profesional__nombre')
    date_hierarchy = 'fecha'
    ordering = ('-fecha', 'hora_inicio')
    
    fieldsets = (
        ('Datos del Turno', {
            'fields': ('profesional', 'fecha', 'hora_inicio', 'hora_fin')
        }),
        ('Cliente', {
            'fields': ('nombre_cliente', 'telefono_cliente', 'nota')
        }),
        ('Estado', {
            'fields': ('estado', 'enviar_recordatorio', 'activo')
        }),
    )