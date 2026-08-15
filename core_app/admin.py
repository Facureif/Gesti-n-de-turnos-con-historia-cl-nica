from django import forms
from django.contrib import admin
from .models import ClienteSaaS, ConfiguracionSistema, Equipamiento

# =============================================
# CONFIGURACIÓN DEL SISTEMA
# =============================================
@admin.register(ConfiguracionSistema)
class ConfiguracionSistemaAdmin(admin.ModelAdmin):
    list_display = ('nombre_sistema', 'modo', 'establecimiento_principal', 'profesional_principal')
    
    def has_add_permission(self, request):
        return not ConfiguracionSistema.objects.exists()


# Inline para equipamientos
class EquipamientoInline(admin.TabularInline):
    model = Equipamiento
    extra = 1  # Muestra un formulario vacío para agregar
    fields = ('nombre', 'descripcion', 'icono', 'imagen', 'orden', 'activo')
    ordering = ('orden', 'id')
    verbose_name = 'Equipamiento / Técnica'
    verbose_name_plural = 'Equipamientos / Técnicas'

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
    inlines = [EquipamientoInline] 
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
            'fields': ('hero_imagen', 'hero_titulo', 'hero_subtitulo', 'hero_badge_texto'),
            'description': 'Imagen de fondo y textos principales de la landing page'
        }),
        ('📝 Textos Landing Consultorio', {
            'fields': (
                'quienes_somos_titulo', 'quienes_somos_subtitulo', 'quienes_somos_texto',
                'nosotros_destacado_1_icono', 'nosotros_destacado_1_titulo', 'nosotros_destacado_1_texto',
                'nosotros_destacado_2_icono', 'nosotros_destacado_2_titulo', 'nosotros_destacado_2_texto',
                'nosotros_destacado_3_icono', 'nosotros_destacado_3_titulo', 'nosotros_destacado_3_texto',
                'horarios_titulo', 'horarios_subtitulo',
                'horarios_lunes_viernes', 'horarios_sabados',
                'servicios_titulo', 'servicios_subtitulo',
                'profesionales_titulo', 'profesionales_subtitulo',
                'footer_texto',
            ),
            'description': 'Personalizá todos los textos que aparecen en la landing del consultorio'
        }),
        ('🧩 Secciones Personalizables', {
            'fields': (
                'servicio_1_icono', 'servicio_1_titulo', 'servicio_1_descripcion', 'mostrar_servicio_1',
                'servicio_2_icono', 'servicio_2_titulo', 'servicio_2_descripcion', 'mostrar_servicio_2',
                'servicio_3_icono', 'servicio_3_titulo', 'servicio_3_descripcion', 'mostrar_servicio_3',
                'servicio_4_icono', 'servicio_4_titulo', 'servicio_4_descripcion', 'mostrar_servicio_4',
                'mostrar_precios_landing', 'mostrar_obras_sociales_landing',
                'nosotros_imagen',
            ),
            'description': 'Imagen de "Quiénes Somos", servicios editables, y control de precios'
        }),
        ('📋 Módulos', {
            'fields': ('mostrar_profesionales', 'mostrar_servicios', 'mostrar_horarios', 'mostrar_equipamientos', 'mostrar_selector_temas'),
            'description': 'Activá o desactivá secciones de la landing page y el selector de temas'
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