from django.contrib import admin
from .models import Paciente, PacienteObraSocial


class PacienteObraSocialInline(admin.TabularInline):
    model = PacienteObraSocial
    extra = 0
    fields = ('obra_social', 'plan', 'numero_afiliado', 'sesiones_autorizadas', 'sesiones_restantes', 'fecha_vencimiento', 'activa')


@admin.register(Paciente)
class PacienteAdmin(admin.ModelAdmin):
    list_display = ('nombre_completo', 'dni', 'telefono', 'obra_social', 'activo')
    list_filter = ('obra_social', 'genero', 'activo')
    search_fields = ('nombre', 'apellido', 'dni', 'numero_afiliado', 'telefono')
    ordering = ('apellido', 'nombre')
    readonly_fields = ('creado', 'modificado')
    inlines = [PacienteObraSocialInline]
    
    fieldsets = (
        ('Datos Personales', {
            'fields': ('nombre', 'apellido', 'dni', 'fecha_nacimiento', 
                      'genero', 'telefono', 'email', 'direccion')
        }),
        ('Obra Social Principal', {
            'fields': ('obra_social', 'plan_obra_social', 'numero_afiliado'),
        }),
        ('Contacto de Emergencia', {
            'fields': ('contacto_emergencia_nombre', 'contacto_emergencia_telefono'),
            'classes': ('collapse',)
        }),
        ('Información Adicional', {
            'fields': ('observaciones', 'usuario', 'activo')
        }),
    )


@admin.register(PacienteObraSocial)
class PacienteObraSocialAdmin(admin.ModelAdmin):
    list_display = ('paciente', 'obra_social', 'plan', 'numero_afiliado', 'sesiones_restantes', 'activa')
    list_filter = ('obra_social', 'activa')
    search_fields = ('paciente__nombre', 'paciente__apellido', 'obra_social__nombre')