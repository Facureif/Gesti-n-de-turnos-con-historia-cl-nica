from django.contrib import admin
from .models import HistoriaClinica, Evolucion, ArchivoClinico


class EvolucionInline(admin.TabularInline):
    model = Evolucion
    extra = 0
    fields = ('turno', 'profesional', 'motivo_consulta', 'diagnostico')
    readonly_fields = ('creado',)


class ArchivoClinicoInline(admin.TabularInline):
    model = ArchivoClinico
    extra = 0
    fields = ('tipo', 'descripcion', 'archivo')


@admin.register(HistoriaClinica)
class HistoriaClinicaAdmin(admin.ModelAdmin):
    list_display = ('numero_historia', 'paciente', 'cantidad_evoluciones', 'activo')
    search_fields = ('numero_historia', 'paciente__nombre', 'paciente__apellido')
    inlines = [EvolucionInline]
    
    fieldsets = (
        (None, {
            'fields': ('paciente', 'numero_historia')
        }),
        ('Antecedentes', {
            'fields': ('antecedentes_personales', 'antecedentes_familiares', 
                      'alergias', 'medicacion_habitual')
        }),
    )
    
    def cantidad_evoluciones(self, obj):
        return obj.evoluciones.count()
    cantidad_evoluciones.short_description = 'Evoluciones'


@admin.register(Evolucion)
class EvolucionAdmin(admin.ModelAdmin):
    list_display = ('historia_clinica', 'fecha', 'profesional', 'diagnostico_corto')
    list_filter = ('profesional', 'creado')
    search_fields = ('historia_clinica__paciente__nombre', 'diagnostico')
    inlines = [ArchivoClinicoInline]
    
    def fecha(self, obj):
        return obj.creado.date()
    fecha.short_description = 'Fecha'
    
    def diagnostico_corto(self, obj):
        return obj.diagnostico[:50] + '...' if len(obj.diagnostico) > 50 else obj.diagnostico
    diagnostico_corto.short_description = 'Diagnóstico'
    
    def paciente(self, obj):
        return obj.historia_clinica.paciente
    paciente.short_description = 'Paciente'


@admin.register(ArchivoClinico)
class ArchivoClinicoAdmin(admin.ModelAdmin):
    list_display = ('descripcion', 'tipo', 'evolucion', 'creado')
    list_filter = ('tipo', 'creado')
    search_fields = ('descripcion',)