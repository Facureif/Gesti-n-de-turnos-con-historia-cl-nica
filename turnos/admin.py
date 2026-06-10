from django.contrib import admin
from .models import Turno


@admin.register(Turno)
class TurnoAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'hora_inicio', 'profesional', 'paciente_display', 
                    'estado_coloreado', 'activo')
    list_filter = ('estado', 'profesional', 'fecha', 'activo')
    search_fields = ('paciente__nombre', 'paciente__apellido', 
                    'nombre_no_registrado', 'profesional__nombre')
    date_hierarchy = 'fecha'
    ordering = ('-fecha', 'hora_inicio')
    readonly_fields = ('creado', 'modificado')
    
    fieldsets = (
        ('Datos del Turno', {
            'fields': ('profesional', 'fecha', 'hora_inicio', 'hora_fin')
        }),
        ('Paciente', {
            'fields': ('paciente', 'nombre_no_registrado', 
                      'telefono_no_registrado'),
            'description': 'Completar "Paciente" si está registrado, o los campos de "no registrado" para modalidad rápida'
        }),
        ('Estado y Notas', {
            'fields': ('estado', 'motivo_consulta', 'notas_internas')
        }),
        ('Configuración', {
            'fields': ('enviar_recordatorio', 'activo')
        }),
    )
    
    def paciente_display(self, obj):
        if obj.paciente:
            return obj.paciente.nombre_completo
        elif obj.nombre_no_registrado:
            return f"⚡ {obj.nombre_no_registrado}"
        return "—"
    paciente_display.short_description = 'Paciente'
    paciente_display.admin_order_field = 'paciente__apellido'
    
    def estado_coloreado(self, obj):
        colores = {
            'disponible': '🟢',
            'pendiente': '🟡',
            'confirmado': '🔵',
            'cancelado': '🔴',
            'no_asistio': '⚫',
            'completado': '✅',
            'bloqueado': '🚫',
        }
        return f"{colores.get(obj.estado, '⚪')} {obj.get_estado_display()}"
    estado_coloreado.short_description = 'Estado'
    
    class Media:
        css = {
            'all': ('admin/css/custom_admin.css',)
        }