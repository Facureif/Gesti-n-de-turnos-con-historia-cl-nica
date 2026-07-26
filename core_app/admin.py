from django import forms
from django.contrib import admin
from .models import ClienteSaaS, ConfiguracionSistema

# =============================================
# CONFIGURACIÓN DEL SISTEMA
# =============================================
@admin.register(ConfiguracionSistema)
class ConfiguracionSistemaAdmin(admin.ModelAdmin):
    list_display = ('nombre_sistema', 'modo', 'establecimiento_principal', 'profesional_principal')
    
    def has_add_permission(self, request):
        return not ConfiguracionSistema.objects.exists()


# =============================================
# CLIENTE SAAS
# =============================================
class ClienteSaaSForm(forms.ModelForm):
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
    
    fieldsets = (
        ('📋 Información Básica', {
            'fields': ('slug', 'tipo', 'nombre', 'activo')
        }),
        ('🔗 Vinculación', {
            'fields': ('establecimiento', 'profesional'),
            'description': 'Vinculá este cliente con un establecimiento (consultorio) o un profesional independiente'
        }),
        ('🎨 Tema y Colores', {
            'fields': ('theme_css', 'color_primario', 'color_secundario'),
            'description': 'Elegí un tema predefinido o personalizá los colores manualmente. El color pisa al del theme.'
        }),
        ('🖼️ Hero (Portada)', {
            'fields': ('hero_imagen', 'hero_titulo', 'hero_subtitulo'),
            'description': 'Imagen de fondo y textos principales de la landing page'
        }),
        ('📋 Módulos', {
            'fields': ('mostrar_profesionales', 'mostrar_servicios'),
            'description': 'Activá o desactivá secciones de la landing page'
        }),
        ('📞 Contacto', {
            'fields': ('telefono_contacto', 'email_contacto', 'direccion'),
            'description': 'Estos datos aparecerán en el footer con links directos (WhatsApp, mail, maps)'
        }),
    )
    
    list_display = ('nombre', 'tipo', 'theme_css', 'activo', 'slug')
    list_filter = ('tipo', 'activo', 'theme_css')
    search_fields = ('nombre', 'slug')
    prepopulated_fields = {'slug': ('nombre',)}