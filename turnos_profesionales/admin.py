from django.contrib import admin
from .models import TurnoProfesional, ArchivoTurno


class ArchivoTurnoInline(admin.TabularInline):
    model = ArchivoTurno
    extra = 0
    fields = ('archivo', 'descripcion')


@admin.register(TurnoProfesional)
class TurnoProfesionalAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'hora_inicio', 'profesional', 'paciente', 'monto_coseguro',
                    'establecimiento', 'estado', 'google_event_id',  'obra_social')
    list_filter = ('estado', 'profesional', 'establecimiento', 'obra_social', 'fecha')
    search_fields = ('paciente__nombre', 'paciente__apellido', 'profesional__nombre')
    date_hierarchy = 'fecha'
    ordering = ('-fecha', 'hora_inicio')
    inlines = [ArchivoTurnoInline]
    
    fieldsets = (
        ('Datos del Turno', {
            'fields': ('profesional', 'establecimiento', 'paciente', 'fecha', 'hora_inicio', 'hora_fin', 'monto_coseguro')
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


@admin.register(ArchivoTurno)
class ArchivoTurnoAdmin(admin.ModelAdmin):
    list_display = ('id', 'turno', 'descripcion', 'creado')
    list_filter = ('creado',)
    search_fields = ('descripcion', 'turno__paciente__nombre')