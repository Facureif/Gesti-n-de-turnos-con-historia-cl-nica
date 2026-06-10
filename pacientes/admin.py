from django.contrib import admin
from .models import Paciente


@admin.register(Paciente)
class PacienteAdmin(admin.ModelAdmin):
    list_display = ('nombre_completo', 'dni', 'telefono', 'obra_social', 
                    'sesiones_restantes', 'activo')
    list_filter = ('obra_social', 'genero', 'activo')
    search_fields = ('nombre', 'apellido', 'dni', 'numero_afiliado', 'telefono')
    ordering = ('apellido', 'nombre')
    readonly_fields = ('creado', 'modificado')
    
    fieldsets = (
        ('Datos Personales', {
            'fields': ('nombre', 'apellido', 'dni', 'fecha_nacimiento', 
                      'genero', 'telefono', 'email', 'direccion')
        }),
        ('Sesiones y Obra Social', {
            'fields': ('obra_social', 'plan_obra_social', 'numero_afiliado',
                    'sesiones_autorizadas', 'sesiones_restantes', 
                    'fecha_vencimiento_sesiones'),
        }),
        ('Contacto de Emergencia', {
            'fields': ('contacto_emergencia_nombre', 'contacto_emergencia_telefono'),
            'classes': ('collapse',)
        }),
        ('Información Adicional', {
            'fields': ('observaciones', 'usuario', 'activo')
        }),
    )