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

    hero_titulo = models.CharField(max_length=200, default='Sacá tu turno online', verbose_name='Título principal')
    hero_subtitulo = models.TextField(default='Rápido, fácil y sin esperas', verbose_name='Subtítulo')
    hero_imagen = models.ImageField(upload_to='landing/', blank=True, null=True, verbose_name='Imagen de fondo')
    color_primario = models.CharField(max_length=7, default='#4A90D9', verbose_name='Color principal')
    color_secundario = models.CharField(max_length=7, default='#28a745', verbose_name='Color secundario')
    mostrar_profesionales = models.BooleanField(default=True, verbose_name='Mostrar profesionales')
    mostrar_servicios = models.BooleanField(default=True, verbose_name='Mostrar servicios')
    telefono_contacto = models.CharField(max_length=20, blank=True, verbose_name='Teléfono')
    email_contacto = models.EmailField(blank=True, verbose_name='Email')
    direccion = models.CharField(max_length=200, blank=True, verbose_name='Dirección')
    
    class Meta:
        verbose_name = 'Cliente SaaS'
        verbose_name_plural = 'Clientes SaaS'
    
    def __str__(self):
        return f"{self.nombre} ({self.get_tipo_display()})"    