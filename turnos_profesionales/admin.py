from django.contrib import admin
from .models import TurnoProfesional


@admin.register(TurnoProfesional)
class TurnoProfesionalAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'hora_inicio', 'profesional', 'paciente', 'establecimiento',
                    'tipo_consulta', 'estado', 'obra_social')
    list_filter = ('estado', 'profesional', 'obra_social','establecimiento', 'fecha')
    search_fields = ('paciente__nombre', 'paciente__apellido', 'profesional__nombre')
    date_hierarchy = 'fecha'
    ordering = ('-fecha', 'hora_inicio')
    
    fieldsets = (
        ('Datos del Turno', {
            'fields': ('profesional', 'paciente','establecimiento', 'fecha', 'hora_inicio', 'hora_fin')
        }),
        ('Información', {
            'fields': ('tipo_consulta', 'notas_internas')
        }),
        ('Obra Social', {
            'fields': ('obra_social', 'requiere_autorizacion')
        }),
        ('Estado', {
            'fields': ('estado', 'enviar_recordatorio', 'activo')
        }),
    )