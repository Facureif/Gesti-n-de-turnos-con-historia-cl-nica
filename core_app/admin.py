from django.contrib import admin
from .models import ConfiguracionSistema

@admin.register(ConfiguracionSistema)
class ConfiguracionSistemaAdmin(admin.ModelAdmin):
    list_display = ('nombre_sistema', 'modo', 'establecimiento_principal', 'profesional_principal')
    
    def has_add_permission(self, request):
        # Solo permitir una configuración
        return not ConfiguracionSistema.objects.exists()
    

from django import forms
from django.contrib import admin
from .models import ClienteSaaS

class ClienteSaaSForm(forms.ModelForm):
    """Formulario con widgets mejorados para el admin"""
    class Meta:
        model = ClienteSaaS
        fields = '__all__'
        widgets = {
            'color_primario': forms.TextInput(attrs={'type': 'color'}),
            'color_secundario': forms.TextInput(attrs={'type': 'color'}),
            'hero_subtitulo': forms.Textarea(attrs={'rows': 3}),
        }

@admin.register(ClienteSaaS)
class ClienteSaaSAdmin(admin.ModelAdmin):
    form = ClienteSaaSForm
    
    # Organizar los campos en secciones
    fieldsets = (
        ('Información Básica', {
            'fields': ('slug', 'tipo', 'nombre', 'activo')
        }),
        ('Vinculación', {
            'fields': ('establecimiento', 'profesional'),
            'description': 'Vinculá este cliente con un establecimiento (consultorio) o un profesional independiente'
        }),
        ('🎨 Personalización Visual', {
            'fields': ('color_primario', 'color_secundario'),
            'description': 'Estos colores se usarán en la landing page del consultorio'
        }),
        ('🖼️ Hero (Portada)', {
            'fields': ('hero_imagen', 'hero_titulo', 'hero_subtitulo'),
            'description': 'Configurá la imagen de fondo y textos de la portada'
        }),
        ('📋 Módulos', {
            'fields': ('mostrar_profesionales', 'mostrar_servicios'),
            'description': 'Activá o desactivá secciones de la landing'
        }),
        ('📞 Contacto', {
            'fields': ('telefono_contacto', 'email_contacto', 'direccion')
        }),
    )
    
    list_display = ('nombre', 'tipo', 'activo', 'slug')
    list_filter = ('tipo', 'activo')
    search_fields = ('nombre', 'slug')
    prepopulated_fields = {'slug': ('nombre',)}    