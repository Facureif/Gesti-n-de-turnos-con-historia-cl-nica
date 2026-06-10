from django.contrib import admin
from .models import Profesional


@admin.register(Profesional)
class ProfesionalAdmin(admin.ModelAdmin):
    list_display = ('nombre_completo', 'especialidad', 'matricula','telefono', 'usuario_rol', 'establecimiento', 'activo')
    list_filter = ('especialidad', 'activo')
    search_fields = ('nombre', 'apellido', 'dni', 'matricula')
    ordering = ('apellido', 'nombre')
    
    fieldsets = (
        ('Datos Personales', {
            'fields': ('nombre', 'apellido', 'dni', 'fecha_nacimiento', 
                      'telefono', 'email')
        }),
        ('Datos Profesionales', {
            'fields': ('usuario', 'especialidad', 'matricula', 
                      'color_calendario', 'descripcion')
        }),
        ('Configuración', {
            'fields': ('acepta_obra_social', 'activo')
        }),
        ('Consultorio', {
            'fields': ('establecimiento',)
        }),
    )
    
    def usuario_rol(self, obj):
        return obj.usuario.get_rol_display() if obj.usuario else '—'
    usuario_rol.short_description = 'Rol del Usuario'
    
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if 'usuario' in form.base_fields:
            from usuarios.models import Usuario
            # Mostrar todos los usuarios con rol 'profesional' o sin profesional asignado aún
            form.base_fields['usuario'].queryset = Usuario.objects.filter(
                rol='profesional'
            )
            form.base_fields['usuario'].help_text = (
                'Seleccioná un usuario con rol "profesional". '
                'Si no aparece ninguno, creá primero un Usuario con rol "profesional" desde la sección Usuarios.'
            )
        return form