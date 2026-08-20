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
            'fields': (
                'hero_imagen', 'hero_titulo', 'hero_subtitulo', 'hero_badge_texto',
                'hero_boton_texto', 'hero_scroll_texto'
            ),
            'description': 'Imagen de fondo, textos principales y botón de la portada.'
        }),

        # --- 3. SOBRE MÍ / QUIÉNES SOMOS ---
        ('🧑‍⚕️ Sección "Sobre Mí"', {
            'fields': (
                'sobre_mi_label',
                'quienes_somos_titulo', 'quienes_somos_subtitulo', 'quienes_somos_texto',
                'nosotros_imagen',
                'nosotros_destacado_1_icono', 'nosotros_destacado_1_titulo', 'nosotros_destacado_1_texto',
                'nosotros_destacado_2_icono', 'nosotros_destacado_2_titulo', 'nosotros_destacado_2_texto',
                'nosotros_destacado_3_icono', 'nosotros_destacado_3_titulo', 'nosotros_destacado_3_texto',
            ),
            'description': 'Etiqueta, título, subtítulo, texto e imagen de la sección Sobre Mí, junto con los 3 destacados.'
        }),

        # --- 4. SERVICIOS ---
        ('⚙️ Sección "Servicios"', {
            'fields': (
                'mostrar_servicios', 'servicios_label', 'servicios_titulo', 'servicios_subtitulo',
                'servicio_1_icono', 'servicio_1_titulo', 'servicio_1_descripcion', 'mostrar_servicio_1',
                'servicio_2_icono', 'servicio_2_titulo', 'servicio_2_descripcion', 'mostrar_servicio_2',
                'servicio_3_icono', 'servicio_3_titulo', 'servicio_3_descripcion', 'mostrar_servicio_3',
                'servicio_4_icono', 'servicio_4_titulo', 'servicio_4_descripcion', 'mostrar_servicio_4',
            ),
            'description': 'Activá/Desactivá el bloque completo y editá etiqueta, título, subtítulo y cada tarjeta.'
        }),

        # --- 5. HORARIOS Y UBICACIÓN ---
        ('📍 Sección "Horarios y Ubicación"', {
            'fields': (
                'mostrar_horarios', 'horarios_seccion_label', 'horarios_titulo', 'horarios_subtitulo',
                'horario_lunes_viernes_titulo', 'horario_sabados_titulo',
                'horario_tipo_general', 'horario_online_titulo', 'horario_online_descripcion',
                'ubicaciones_label', 'ubicaciones_titulo', 'ubicaciones_subtitulo',
                'horarios_label', 'mostrar_mapa_horarios',
            ),
            'description': 'Etiquetas, títulos y textos de las tarjetas de horarios y ubicaciones.'
        }),

        # --- 6. PROFESIONALES ---
        ('👨‍⚕️ Sección "Profesionales"', {
            'fields': (
                'mostrar_profesionales', 'profesionales_label', 'profesionales_titulo', 'profesionales_subtitulo',
                'boton_orden_llegada_texto', 'texto_whatsapp', 'texto_horarios_no_disponibles',
            ),
            'description': 'Etiqueta, título, subtítulo y textos de la sección de profesionales.'
        }),

        # --- 7. COBERTURA Y PRECIOS ---
        ('💰 Sección "Cobertura"', {
            'fields': (
                'mostrar_cobertura', 'cobertura_label', 'cobertura_titulo', 'cobertura_subtitulo',
                'mostrar_precios_landing', 'mostrar_obras_sociales_landing'
            ),
            'description': 'Etiqueta, título y subtítulo de la sección Cobertura. Controlá la visibilidad de aranceles y obras sociales.'
        }),

        # --- 8. EQUIPAMIENTOS ---
        ('🛠️ Sección "Equipamientos"', {
            'fields': (
                'mostrar_equipamientos', 'equipamientos_label', 'equipamientos_titulo', 'equipamientos_subtitulo',
                'texto_no_equipamientos',
            ),
            'description': 'Etiqueta, título, subtítulo y texto cuando no hay equipos. Los equipos se cargan en el Inline debajo.'
        }),

        # --- 9. FOOTER Y CONTACTO ---
        ('📞 Footer y Contacto', {
            'fields': (
                'footer_texto', 'telefono_contacto', 'email_contacto', 'direccion',
                'instagram_url', 'facebook_url', 'mostrar_horarios_footer',
                'footer_horarios_titulo', 'footer_contacto_titulo',
                'footer_desarrollado_texto', 'footer_turnos_online_texto',
            ),
            'description': 'Datos de contacto, redes sociales, textos y títulos del pie de página.'
        }),

        # --- 10. MÓDULOS AVANZADOS ---
        ('🔧 Módulos Avanzados', {
            'fields': ('mostrar_selector_temas', 'boton_flotante_texto'),
            'description': 'Opciones extra como el selector de temas flotante y texto del botón flotante.'
        }),
    )
    
    list_display = ('nombre', 'tipo', 'theme_css', 'activo', 'slug')
    list_filter = ('tipo', 'activo', 'theme_css')
    search_fields = ('nombre', 'slug')
    prepopulated_fields = {'slug': ('nombre',)}