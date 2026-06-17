from django.contrib import admin
from .models import Agenda, HorarioAtencion, BloqueoAgenda


class HorarioAtencionInline(admin.TabularInline):
    model = HorarioAtencion
    extra = 1
    fields = ('dia', 'hora_inicio', 'hora_fin', 'duracion_turno')


class BloqueoAgendaInline(admin.TabularInline):
    model = BloqueoAgenda
    extra = 0
    fields = ('fecha', 'hora_inicio', 'hora_fin', 'motivo')


@admin.register(Agenda)
class AgendaAdmin(admin.ModelAdmin):
    list_display = ('profesional', 'fecha_inicio', 'fecha_fin', 'pacientes_simultaneos',
                    'cantidad_horarios', 'activo')
    list_filter = ('profesional__especialidad', 'activo')
    search_fields = ('profesional__nombre', 'profesional__apellido')
    inlines = [HorarioAtencionInline, BloqueoAgendaInline]
    
    fieldsets = (
        (None, {
            'fields': ('profesional', 'fecha_inicio', 'fecha_fin', 'pacientes_simultaneos')
        }),
        ('Configuración', {
            'fields': ('acepta_sobreturnos', 'tiempo_entre_turnos', 'activo')
        }),
    )
    
    def cantidad_horarios(self, obj):
        return obj.horarios.count()
    cantidad_horarios.short_description = 'Horarios configurados'


@admin.register(HorarioAtencion)
class HorarioAtencionAdmin(admin.ModelAdmin):
    list_display = ('agenda', 'dia', 'hora_inicio', 'hora_fin', 'duracion_turno')
    list_filter = ('dia', 'agenda__profesional')
    ordering = ('agenda', 'dia', 'hora_inicio')


@admin.register(BloqueoAgenda)
class BloqueoAgendaAdmin(admin.ModelAdmin):
    list_display = ('agenda', 'fecha', 'motivo', 'activo')
    list_filter = ('agenda__profesional', 'fecha')
    search_fields = ('motivo',)
    date_hierarchy = 'fecha'