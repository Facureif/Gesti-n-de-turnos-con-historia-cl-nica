from django.db import models


class ModeloBase(models.Model):
    """Modelo abstracto del que heredan todos los demás"""
    creado = models.DateTimeField(auto_now_add=True, verbose_name='Creado')
    modificado = models.DateTimeField(auto_now=True, verbose_name='Modificado')
    activo = models.BooleanField(default=True, verbose_name='Activo')
    
    class Meta:
        abstract = True


class Persona(ModeloBase):
    """Modelo abstracto para personas (profesionales y pacientes)"""
    nombre = models.CharField(max_length=100, verbose_name='Nombre')
    apellido = models.CharField(max_length=100, verbose_name='Apellido')
    dni = models.CharField(max_length=20, unique=True, verbose_name='DNI')
    fecha_nacimiento = models.DateField(verbose_name='Fecha de Nacimiento')
    telefono = models.CharField(max_length=20, verbose_name='Teléfono')
    email = models.EmailField(blank=True, verbose_name='Email')
    
    class Meta:
        abstract = True
    
    @property
    def nombre_completo(self):
        return f"{self.nombre} {self.apellido}"
    
    def __str__(self):
        return self.nombre_completo

class ConfiguracionSistema(ModeloBase):
    MODOS = [
        ('consultorio', 'Consultorio (varios profesionales)'),
        ('profesional', 'Profesional Independiente'),
    ]
    
    modo = models.CharField(max_length=20, choices=MODOS, default='profesional', verbose_name='Modo del Sistema')
    establecimiento_principal = models.ForeignKey(
        'establecimientos.Establecimiento',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Consultorio Principal'
    )
    profesional_principal = models.ForeignKey(
        'profesionales.Profesional',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Profesional Principal'
    )
    nombre_sistema = models.CharField(max_length=200, default='Sistema de Gestión de Turnos', verbose_name='Nombre del Sistema')
    
    class Meta:
        verbose_name = 'Configuración del Sistema'
        verbose_name_plural = 'Configuración del Sistema'
    
    def __str__(self):
        return self.nombre_sistema
    
    @classmethod
    def obtener(cls):
        """Obtiene la configuración actual o crea una por defecto."""
        config = cls.objects.first()
        if not config:
            config = cls.objects.create()
        return config        
    
class ClienteSaaS(ModeloBase):
    
    TIPOS = [
        ('consultorio', 'Consultorio'),
        ('profesional', 'Profesional Independiente'),
    ]
    
    slug = models.SlugField(unique=True, verbose_name='Identificador URL')
    tipo = models.CharField(max_length=20, choices=TIPOS, verbose_name='Tipo')
    nombre = models.CharField(max_length=200, verbose_name='Nombre')
    establecimiento = models.ForeignKey(
        'establecimientos.Establecimiento',
        on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name='Consultorio'
    )
    profesional = models.ForeignKey(
        'profesionales.Profesional',
        on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name='Profesional'
    )
    activo = models.BooleanField(default=True)

    theme_css = models.CharField(
    max_length=50,
    default='default',
    verbose_name='Tema Visual',
    choices=[
        ('default', '🔵 Blanco Profesional'),
        ('azul_oscuro', '🌟 Azul Oscuro Premium'),
        ('verde_oscuro', '🟢 Verde Médico Clásico'),
        ('blanco_negro', '⬜⬛ Blanco & Negro Minimalista'),
    ]
)
    # 🖼️ Hero
    hero_titulo = models.CharField(max_length=200, default='Sacá tu turno online', verbose_name='Título principal')
    hero_subtitulo = models.TextField(default='Rápido, fácil y sin esperas', verbose_name='Subtítulo')
    hero_imagen = models.ImageField(upload_to='landing/', blank=True, null=True, verbose_name='Imagen de fondo')
    
    # 🎨 Colores (se usan si no hay theme o para pisar colores del theme)
    color_primario = models.CharField(max_length=7, default='#4A90D9', verbose_name='Color principal')
    color_secundario = models.CharField(max_length=7, default='#28a745', verbose_name='Color secundario')
    
    # 📋 Módulos
    mostrar_profesionales = models.BooleanField(default=True, verbose_name='Mostrar profesionales')
    mostrar_servicios = models.BooleanField(default=True, verbose_name='Mostrar servicios')
    
    # 📞 Contacto
    telefono_contacto = models.CharField(max_length=20, blank=True, verbose_name='Teléfono')
    email_contacto = models.EmailField(blank=True, verbose_name='Email')
    direccion = models.CharField(max_length=200, blank=True, verbose_name='Dirección')

    quienes_somos_titulo = models.CharField(max_length=200, default='Nuestro Consultorio')
    quienes_somos_subtitulo = models.CharField(max_length=200, default='Comprometidos con tu salud y bienestar')
    quienes_somos_texto = models.TextField(blank=True, default='En nuestro consultorio nos dedicamos a brindar atención médica de calidad...')
    
    horarios_titulo = models.CharField(max_length=200, default='¿Cuándo atendemos?')
    horarios_subtitulo = models.CharField(max_length=200, default='Consultá nuestros horarios de atención al público')
    horarios_lunes_viernes = models.CharField(max_length=100, default='8:00 - 20:00 hs')
    horarios_sabados = models.CharField(max_length=100, default='8:00 - 13:00 hs')
    mostrar_horarios = models.BooleanField(default=True)
    
    servicios_titulo = models.CharField(max_length=200, default='¿Qué ofrecemos?')
    servicios_subtitulo = models.CharField(max_length=200, default='Conocé todo lo que podemos hacer por tu salud')
    
    profesionales_titulo = models.CharField(max_length=200, default='Nuestros Profesionales')
    profesionales_subtitulo = models.CharField(max_length=200, default='Filtrá por especialidad y elegí con quién querés atenderte')
    
    footer_texto = models.CharField(max_length=200, blank=True, default='Atención profesional de calidad. Tu salud es nuestra prioridad.')
    
    # Control del selector de temas (demo)
    mostrar_selector_temas = models.BooleanField(default=True, help_text='Mostrar el selector de temas flotante en la landing')
    
    # Ya existentes (asegurate de tenerlos)
    hero_badge_texto = models.CharField(max_length=100, default='Turnos Online 24/7')
    # Imagen para la sección "Quiénes Somos" (independiente del hero)
    nosotros_imagen = models.ImageField(
        upload_to='landing/nosotros/', blank=True, null=True,
        verbose_name='Imagen de Quiénes Somos'
    )

    # Destacados (los tres ítems de la sección "Quiénes Somos")
    nosotros_destacado_1_icono = models.CharField(max_length=30, default='fas fa-user-md', verbose_name='Ícono destacado 1')
    nosotros_destacado_1_titulo = models.CharField(max_length=100, default='Profesionales Expertos')
    nosotros_destacado_1_texto = models.CharField(max_length=200, default='Especialistas en diversas áreas de la salud')

    nosotros_destacado_2_icono = models.CharField(max_length=30, default='fas fa-clock', verbose_name='Ícono destacado 2')
    nosotros_destacado_2_titulo = models.CharField(max_length=100, default='Turnos Online')
    nosotros_destacado_2_texto = models.CharField(max_length=200, default='Reservá tu turno cuando quieras, desde donde estés')

    nosotros_destacado_3_icono = models.CharField(max_length=30, default='fas fa-shield-alt', verbose_name='Ícono destacado 3')
    nosotros_destacado_3_titulo = models.CharField(max_length=100, default='Atención Segura')
    nosotros_destacado_3_texto = models.CharField(max_length=200, default='Protocolos de higiene y bioseguridad')

    # Servicios (cuatro tarjetas, cada una con título, descripción e ícono)
    servicio_1_icono = models.CharField(max_length=30, default='🏥', verbose_name='Servicio 1 - Ícono')
    servicio_1_titulo = models.CharField(max_length=100, default='Atención Personalizada')
    servicio_1_descripcion = models.TextField(default='Cada paciente recibe un tratamiento adaptado a sus necesidades específicas.', verbose_name='Servicio 1 - Descripción')
    mostrar_servicio_1 = models.BooleanField(default=True, verbose_name='Mostrar Servicio 1')

    servicio_2_icono = models.CharField(max_length=30, default='📱', verbose_name='Servicio 2 - Ícono')
    servicio_2_titulo = models.CharField(max_length=100, default='Turnos Online')
    servicio_2_descripcion = models.TextField(default='Reservá, modificá o cancelá tus turnos desde cualquier dispositivo, 24/7.', verbose_name='Servicio 2 - Descripción')
    mostrar_servicio_2 = models.BooleanField(default=True, verbose_name='Mostrar Servicio 2')

    servicio_3_icono = models.CharField(max_length=30, default='📋', verbose_name='Servicio 3 - Ícono')
    servicio_3_titulo = models.CharField(max_length=100, default='Historia Clínica Digital')
    servicio_3_descripcion = models.TextField(default='Accedé a tu historial médico de forma segura cuando lo necesites.', verbose_name='Servicio 3 - Descripción')
    mostrar_servicio_3 = models.BooleanField(default=True, verbose_name='Mostrar Servicio 3')

    servicio_4_icono = models.CharField(max_length=30, default='🏥', verbose_name='Servicio 4 - Ícono')
    servicio_4_titulo = models.CharField(max_length=100, default='Obras Sociales')
    servicio_4_descripcion = models.TextField(default='Trabajamos con las principales obras sociales y prepagas.', verbose_name='Servicio 4 - Descripción')
    mostrar_servicio_4 = models.BooleanField(default=True, verbose_name='Mostrar Servicio 4')

    # Control de visibilidad de precios y obras sociales en la landing
    mostrar_precios_landing = models.BooleanField(default=True, verbose_name='Mostrar precios en la landing')
    mostrar_obras_sociales_landing = models.BooleanField(default=True, verbose_name='Mostrar obras sociales en la landing')

    mostrar_equipamientos = models.BooleanField(default=True, verbose_name='Mostrar sección de equipamientos')
    equipamientos_titulo = models.CharField(max_length=200, default='Nuestros Equipos')
    equipamientos_subtitulo = models.CharField(max_length=200, default='Contamos con tecnología de última generación')
    class Meta:
        verbose_name = 'Cliente SaaS'
        verbose_name_plural = 'Clientes SaaS'
    
    def __str__(self):
        return f"{self.nombre} ({self.get_tipo_display()})"


class Equipamiento(ModeloBase):
    """
    Instrumentos, equipos o técnicas que el consultorio quiere destacar.
    Ej: Botas de compresión, crioterapia, tomógrafo, etc.
    """
    cliente = models.ForeignKey(
        ClienteSaaS,
        on_delete=models.CASCADE,
        related_name='equipamientos',
        verbose_name='Cliente'
    )
    nombre = models.CharField(max_length=200, verbose_name='Nombre')
    descripcion = models.TextField(blank=True, verbose_name='Descripción')
    icono = models.CharField(
        max_length=30,
        blank=True,
        default='🩺',
        verbose_name='Icono (emoji o clase FontAwesome)',
        help_text='Podés usar un emoji (🩺) o una clase de FontAwesome (fas fa-x-ray)'
    )
    imagen = models.ImageField(
        upload_to='equipamientos/',
        blank=True,
        null=True,
        verbose_name='Imagen (opcional)'
    )
    orden = models.PositiveIntegerField(default=0, verbose_name='Orden')

    class Meta:
        verbose_name = 'Equipamiento / Técnica'
        verbose_name_plural = 'Equipamientos / Técnicas'
        ordering = ['orden', 'id']

    def __str__(self):
        return f"{self.nombre} ({self.cliente.nombre})"
