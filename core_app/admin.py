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
    extra = 1
    fields = ('nombre', 'descripcion', 'icono', 'imagen', 'orden', 'activo')
    ordering = ('orden', 'id')
    verbose_name = 'Equipamiento / Técnica'
    verbose_name_plural = 'Equipamientos / Técnicas'


# =============================================
# CLIENTE SAAS - ADMIN REORGANIZADO POR SECCIONES
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
        # --- 1. DATOS GENERALES Y DISEÑO ---
        ('📋 Configuración General', {
            'fields': ('layout_estilo', 'favicon', 'slug', 'tipo', 'nombre', 'activo'),
            'description': 'Configuración básica de identidad y diseño del sitio web.'
        }),
        ('🔗 Vinculación', {
            'fields': ('establecimiento', 'profesional'),
            'description': 'Vinculá este cliente con un establecimiento o un profesional independiente.'
        }),
        ('🎨 Tema Visual', {
            'fields': ('theme_css', 'color_primario', 'color_secundario'),
            'description': 'Elegí un tema predefinido o personalizá los colores manualmente.'
        }),

        # --- 2. PORTADA (HERO) ---
        ('🖼️ Hero (Portada)', {
            'fields': ('hero_imagen', 'hero_titulo', 'hero_subtitulo', 'hero_badge_texto'),
            'description': 'Imagen de fondo y textos principales de la portada.'
        }),

        # --- 3. SOBRE MÍ ---
        ('🧑‍⚕️ Sección "Sobre Mí"', {
            'fields': (
                'quienes_somos_titulo', 'quienes_somos_subtitulo', 'quienes_somos_texto',
                'nosotros_imagen',
                'nosotros_destacado_1_icono', 'nosotros_destacado_1_titulo', 'nosotros_destacado_1_texto',
                'nosotros_destacado_2_icono', 'nosotros_destacado_2_titulo', 'nosotros_destacado_2_texto',
                'nosotros_destacado_3_icono', 'nosotros_destacado_3_titulo', 'nosotros_destacado_3_texto',
            ),
            'description': 'Texto biográfico y las 3 tarjetas destacadas (ej: Expertos, Turnos Online, Seguridad).'
        }),

        # --- 4. SERVICIOS (Títulos + Checkbox) ---
        ('⚙️ Sección "Servicios"', {
            'fields': (
                'mostrar_servicios', 'servicios_titulo', 'servicios_subtitulo',
                'servicio_1_icono', 'servicio_1_titulo', 'servicio_1_descripcion', 'mostrar_servicio_1',
                'servicio_2_icono', 'servicio_2_titulo', 'servicio_2_descripcion', 'mostrar_servicio_2',
                'servicio_3_icono', 'servicio_3_titulo', 'servicio_3_descripcion', 'mostrar_servicio_3',
                'servicio_4_icono', 'servicio_4_titulo', 'servicio_4_descripcion', 'mostrar_servicio_4',
            ),
            'description': 'Activá/Desactivá el bloque completo y editá cada una de las 4 tarjetas de servicio.'
        }),

        # --- 5. HORARIOS Y UBICACIÓN ---
        ('📍 Sección "Horarios y Ubicación"', {
            'fields': ('mostrar_horarios', 'horarios_titulo', 'horarios_subtitulo'),
            'description': 'Títulos del bloque de horarios (los horarios reales se cargan en la sección Establecimientos).'
        }),

        # --- 6. COBERTURA Y PRECIOS ---
        ('💰 Sección "Cobertura"', {
            'fields': (
                'mostrar_cobertura', 'cobertura_titulo', 'cobertura_subtitulo',
                'mostrar_precios_landing', 'mostrar_obras_sociales_landing'
            ),
            'description': 'Controlá la visibilidad de los aranceles y las obras sociales en la página.'
        }),

        # --- 7. EQUIPAMIENTOS ---
        ('🛠️ Sección "Equipamientos"', {
            'fields': ('mostrar_equipamientos', 'equipamientos_titulo', 'equipamientos_subtitulo'),
            'description': 'Títulos de la sección. Los equipos/imágenes se cargan en el Inline (tabla) ubicado abajo.'
        }),

        # --- 8. FOOTER Y CONTACTO ---
        ('📞 Footer y Contacto', {
            'fields': (
                'footer_texto', 'telefono_contacto', 'email_contacto', 'direccion',
                'instagram_url', 'facebook_url', 'mostrar_horarios_footer'
            ),
            'description': 'Datos de contacto, redes sociales y texto resumido para el pie de página.'
        }),

        # --- 9. MÓDULOS AVANZADOS ---
        ('🔧 Módulos Avanzados', {
            'fields': ('mostrar_profesionales', 'mostrar_selector_temas'),
            'description': 'Opciones extra como el selector de temas flotante (para demos o personalización).'
        }),
    )
    
    list_display = ('nombre', 'tipo', 'theme_css', 'activo', 'slug')
    list_filter = ('tipo', 'activo', 'theme_css')
    search_fields = ('nombre', 'slug')
    prepopulated_fields = {'slug': ('nombre',)}