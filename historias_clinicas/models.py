from datetime import date

from django.db import models
from core_app.models import ModeloBase


class HistoriaClinica(ModeloBase):
    paciente = models.OneToOneField(
        'pacientes.Paciente',
        on_delete=models.CASCADE,
        verbose_name='Paciente'
    )
    numero_historia = models.CharField(
        max_length=20,
        unique=True,
        verbose_name='Número de Historia'
    )
    antecedentes_personales = models.TextField(
        blank=True,
        verbose_name='Antecedentes Personales'
    )
    antecedentes_familiares = models.TextField(
        blank=True,
        verbose_name='Antecedentes Familiares'
    )
    alergias = models.TextField(blank=True, verbose_name='Alergias')
    medicacion_habitual = models.TextField(
        blank=True,
        verbose_name='Medicación Habitual'
    )
    
    class Meta:
        verbose_name = 'Historia Clínica'
        verbose_name_plural = 'Historias Clínicas'
    
    def __str__(self):
        return f"HC #{self.numero_historia} - {self.paciente}"


class Evolucion(ModeloBase):
    historia_clinica = models.ForeignKey(
        HistoriaClinica,
        on_delete=models.CASCADE,
        related_name='evoluciones',
        verbose_name='Historia Clínica'
    )
    turno = models.OneToOneField(
        'turnos_profesionales.TurnoProfesional',  # ← CORREGIDO
        on_delete=models.CASCADE,
        verbose_name='Turno'
    )
    profesional = models.ForeignKey(
        'profesionales.Profesional',
        on_delete=models.CASCADE,
        verbose_name='Profesional'
    )
    medicacion_recetada = models.TextField(
    blank=True,
    verbose_name='Medicación Recetada'
)
    motivo_consulta = models.TextField(verbose_name='Motivo de Consulta')
    diagnostico = models.TextField(blank=True, verbose_name='Diagnóstico')
    tratamiento_realizado = models.TextField(
        blank=True,
        verbose_name='Tratamiento Realizado'
    )
    indicaciones = models.TextField(blank=True, verbose_name='Indicaciones')
    proximo_control = models.DateField(
        null=True,
        blank=True,
        verbose_name='Próximo Control'
    )
    
    class Meta:
        verbose_name = 'Evolución'
        verbose_name_plural = 'Evoluciones'
        ordering = ['-creado']
    
    def __str__(self):
        return f"Evolución {self.creado.date()} - {self.paciente}"


class ArchivoClinico(ModeloBase):
    TIPOS = [
        ('rx', 'Radiografía'),
        ('foto', 'Fotografía'),
        ('estudio', 'Estudio'),
        ('receta', 'Receta'),
        ('otro', 'Otro'),
    ]
    
    evolucion = models.ForeignKey(
        Evolucion,
        on_delete=models.CASCADE,
        related_name='archivos',
        verbose_name='Evolución'
    )
    archivo = models.FileField(upload_to='hc/%Y/%m/', verbose_name='Archivo')
    descripcion = models.CharField(max_length=200, verbose_name='Descripción')
    tipo = models.CharField(max_length=20, choices=TIPOS, verbose_name='Tipo')
    
    class Meta:
        verbose_name = 'Archivo Clínico'
        verbose_name_plural = 'Archivos Clínicos'
    
    def __str__(self):
        return f"{self.get_tipo_display()} - {self.descripcion}"
    
# historias_clinicas/models.py
from django.db import models
from pacientes.models import Paciente
from profesionales.models import Profesional

class FichaTecnica(models.Model):
    """Ficha técnica específica por especialidad"""
    
    paciente = models.OneToOneField(
        Paciente,
        on_delete=models.CASCADE,
        related_name='ficha_tecnica'
    )
    profesional = models.ForeignKey(
        Profesional,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    especialidad = models.CharField(max_length=30)
    
    # Datos específicos guardados como JSON
    datos_especificos = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Datos Específicos'
    )
    
    notas_generales = models.TextField(
        blank=True,
        verbose_name='Notas Generales'
    )
    
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Ficha Técnica'
        verbose_name_plural = 'Fichas Técnicas'
    
    def __str__(self):
        return f"Ficha {self.especialidad} - {self.paciente}"
    
    def get_dato(self, clave, default=None):
        """Obtener un dato específico del JSON"""
        return self.datos_especificos.get(clave, default)


class Lesion(models.Model):
    """Historial de lesiones del paciente."""
    TIPOS_LESION = [
        ('muscular', 'Muscular'),
        ('articular', 'Articular'),
        ('tendinosa', 'Tendinosa'),
        ('ligamentaria', 'Ligamentaria'),
        ('osea', 'Ósea'),
        ('postural', 'Postural'),
        ('otra', 'Otra'),
    ]
    
    paciente = models.ForeignKey(
        'pacientes.Paciente',
        on_delete=models.CASCADE,
        related_name='lesiones'
    )
    fecha_lesion = models.DateField(verbose_name='Fecha de la lesión')
    tipo_lesion = models.CharField(max_length=20, choices=TIPOS_LESION, default='otra')
    zona = models.CharField(max_length=100, verbose_name='Zona afectada')
    descripcion = models.TextField(verbose_name='Descripción')
    tratamiento = models.TextField(blank=True, verbose_name='Tratamiento realizado')
    resuelta = models.BooleanField(default=False, verbose_name='¿Resuelta?')
    fecha_resolucion = models.DateField(null=True, blank=True)
    creado = models.DateTimeField(auto_now_add=True)
    archivo = models.FileField(upload_to='tratamientos_odontologicos/%Y/%m/', null=True, blank=True)

    class Meta:
        ordering = ['-fecha_lesion']
        verbose_name = 'Lesión'
        verbose_name_plural = 'Lesiones'
    
    def __str__(self):
        estado = '✅' if self.resuelta else '⚠️'
        return f"{estado} {self.zona} - {self.fecha_lesion.strftime('%d/%m/%Y')}"

class SeguimientoTratamiento(models.Model):
    """Registro de evolución del tratamiento kinesiológico."""
    paciente = models.ForeignKey(
        'pacientes.Paciente',
        on_delete=models.CASCADE,
        related_name='seguimientos'
    )
    lesion = models.ForeignKey(
        'Lesion',
        on_delete=models.CASCADE,
        related_name='seguimientos',
        verbose_name='Lesión relacionada'
    )
    fecha = models.DateField(default=date.today, verbose_name='Fecha')
    
    # Datos del tratamiento
    peso_trabajo_kg = models.DecimalField(
        max_digits=5, decimal_places=1, null=True, blank=True,
        verbose_name='Peso de trabajo (kg)'
    )
    series = models.IntegerField(null=True, blank=True, verbose_name='Series')
    repeticiones = models.IntegerField(null=True, blank=True, verbose_name='Repeticiones')
    
    # Escalas de evaluación
    nivel_dolor = models.IntegerField(
        null=True, blank=True,
        choices=[(i, str(i)) for i in range(0, 11)],
        verbose_name='Nivel de dolor (0-10)'
    )
    rango_movimiento = models.CharField(
        max_length=20, blank=True,
        choices=[
            ('muy_limitado', 'Muy limitado'),
            ('limitado', 'Limitado'),
            ('moderado', 'Moderado'),
            ('bueno', 'Bueno'),
            ('completo', 'Completo'),
        ],
        verbose_name='Rango de movimiento'
    )
    
    # Observaciones
    observaciones = models.TextField(blank=True, verbose_name='Observaciones')
    ejercicios_realizados = models.TextField(blank=True, verbose_name='Ejercicios realizados')
    
    creado = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-fecha', '-creado']
        verbose_name = 'Seguimiento'
        verbose_name_plural = 'Seguimientos'
    
    def __str__(self):
        return f"Seguimiento {self.fecha.strftime('%d/%m/%Y')} - {self.lesion.zona}"        
    

class TratamientoOdontologico(models.Model):
    """Registro de tratamientos realizados por pieza dental."""
    paciente = models.ForeignKey(
        'pacientes.Paciente',
        on_delete=models.CASCADE,
        related_name='tratamientos_odontologicos'
    )
    profesional = models.ForeignKey(
        'profesionales.Profesional',
        on_delete=models.SET_NULL,
        null=True,
        related_name='tratamientos_realizados'
    )
    fecha = models.DateField(default=date.today)
    pieza_dental = models.CharField(max_length=10, verbose_name='Pieza dental')
    archivo = models.FileField(upload_to='tratamientos_odontologicos/%Y/%m/', null=True, blank=True)

    TIPO_TRATAMIENTO = [
        ('caries', 'Caries / Obturación'),
        ('endodoncia', 'Endodoncia / Conducto'),
        ('extraccion', 'Extracción'),
        ('corona', 'Corona / Prótesis fija'),
        ('puente', 'Puente'),
        ('implante', 'Implante'),
        ('protesis_removible', 'Prótesis removible'),
        ('ortodoncia', 'Ortodoncia / Brackets'),
        ('blanqueamiento', 'Blanqueamiento'),
        ('sellador', 'Sellador / Prevención'),
        ('limpieza', 'Limpieza / Profilaxis'),
        ('tratamiento_encia', 'Tratamiento de encías'),
        ('otro', 'Otro'),
    ]
    tipo_tratamiento = models.CharField(max_length=30, choices=TIPO_TRATAMIENTO)
    descripcion = models.TextField(blank=True)
    material_usado = models.CharField(max_length=100, blank=True, verbose_name='Material usado')
    costo = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    requiere_seguimiento = models.BooleanField(default=False)
    fecha_proximo_control = models.DateField(null=True, blank=True)
    completado = models.BooleanField(default=True)
    
    creado = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-fecha']
        verbose_name = 'Tratamiento Odontológico'
        verbose_name_plural = 'Tratamientos Odontológicos'
    
    def __str__(self):
        return f"{self.get_tipo_tratamiento_display()} - Pieza {self.pieza_dental} - {self.fecha.strftime('%d/%m/%Y')}"    

class ConsultaNutricional(models.Model):
    OBJETIVOS = [
        ('bajar_peso', 'Bajar de peso'),
        ('aumentar_peso', 'Aumentar de peso'),
        ('mantener', 'Mantener peso'),
        ('reducir_grasa', 'Reducir % grasa'),
        ('ganar_musculo', 'Ganar masa muscular'),
        ('deportivo', 'Rendimiento deportivo'),
        ('patologia', 'Manejo de patología'),
        ('otro', 'Otro'),
    ]
    
    paciente = models.ForeignKey(
        'pacientes.Paciente', on_delete=models.CASCADE,
        related_name='consultas_nutricionales'
    )
    profesional = models.ForeignKey(
        'profesionales.Profesional', on_delete=models.SET_NULL,
        null=True, related_name='consultas_nutricionales_realizadas'
    )
    fecha = models.DateField(default=date.today)
    
    # Datos antropométricos
    peso_kg = models.DecimalField(max_digits=5, decimal_places=1, verbose_name='Peso (kg)')
    altura_cm = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True, verbose_name='Altura (cm)')
    imc = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True, verbose_name='IMC')
    perimetro_cintura_cm = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True, verbose_name='Cintura (cm)')
    perimetro_cadera_cm = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True, verbose_name='Cadera (cm)')
    icc = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True, verbose_name='Índice Cintura/Cadera')
    porcentaje_grasa = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True, verbose_name='% Grasa corporal')
    porcentaje_musculo = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True, verbose_name='% Masa muscular')
    
    # Seguimiento
    peso_inicial_kg = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True, verbose_name='Peso inicial (kg)')
    es_seguimiento = models.BooleanField(default=False, verbose_name='¿Es consulta de seguimiento?')
    consulta_base = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='seguimientos', verbose_name='Consulta inicial')
    
    # Evaluación
    objetivo = models.CharField(max_length=30, choices=OBJETIVOS, blank=True)
    expectativas_metas = models.TextField(blank=True, verbose_name='Expectativas / Metas del paciente')
    plan_nutricional = models.TextField(blank=True, verbose_name='Plan nutricional indicado')
    medicacion_suplementos = models.TextField(blank=True, verbose_name='Medicación / Suplementos que toma')
    laboratorios = models.TextField(blank=True, verbose_name='Resultados de laboratorios recientes')
    observaciones = models.TextField(blank=True)
    
    archivo = models.FileField(upload_to='consultas_nutricionales/%Y/%m/', null=True, blank=True)
    creado = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-fecha']
        verbose_name = 'Consulta Nutricional'
        verbose_name_plural = 'Consultas Nutricionales'
    
    def __str__(self):
        return f"Consulta {self.fecha.strftime('%d/%m/%Y')} - {self.paciente.nombre_completo}"
    
    def calcular_imc(self):
        if self.peso_kg and self.altura_cm and self.altura_cm > 0:
            altura_m = float(self.altura_cm) / 100
            return round(float(self.peso_kg) / (altura_m ** 2), 1)
        return None
    
    def calcular_icc(self):
        if self.perimetro_cintura_cm and self.perimetro_cadera_cm and self.perimetro_cadera_cm > 0:
            return round(float(self.perimetro_cintura_cm) / float(self.perimetro_cadera_cm), 2)
        return None
    
    def save(self, *args, **kwargs):
        if not self.imc:
            self.imc = self.calcular_imc()
        if not self.icc:
            self.icc = self.calcular_icc()
        super().save(*args, **kwargs)

class EvaluacionFonoaudiologica(models.Model):
    """Registro de evaluaciones y tratamientos fonoaudiológicos."""
    paciente = models.ForeignKey(
        'pacientes.Paciente',
        on_delete=models.CASCADE,
        related_name='evaluaciones_fonoaudiologicas'
    )
    profesional = models.ForeignKey(
        'profesionales.Profesional',
        on_delete=models.SET_NULL,
        null=True,
        related_name='evaluaciones_fono'
    )
    fecha = models.DateField(default=date.today)
    archivo = models.FileField(upload_to='tratamientos_odontologicos/%Y/%m/', null=True, blank=True)
    
    AREAS = [
        ('lenguaje', 'Lenguaje'),
        ('habla', 'Habla'),
        ('voz', 'Voz'),
        ('deglucion', 'Deglución'),
        ('audicion', 'Audición'),
        ('aprendizaje', 'Aprendizaje'),
        ('otra', 'Otra'),
    ]
    area = models.CharField(max_length=20, choices=AREAS, verbose_name='Área')
    
    DIAGNOSTICOS = [
        ('retraso_lenguaje', 'Retraso del lenguaje'),
        ('trastorno_habla', 'Trastorno del habla'),
        ('disfonia', 'Disfonía'),
        ('disfagia', 'Disfagia'),
        ('tartamudez', 'Tartamudez'),
        ('trastorno_aprendizaje', 'Trastorno del aprendizaje'),
        ('hipoacusia', 'Hipoacusia'),
        ('otro', 'Otro'),
    ]
    diagnostico = models.CharField(max_length=30, choices=DIAGNOSTICOS, blank=True)
    
    evaluacion = models.TextField(blank=True, verbose_name='Evaluación / Observaciones')
    objetivos = models.TextField(blank=True, verbose_name='Objetivos del tratamiento')
    ejercicios = models.TextField(blank=True, verbose_name='Ejercicios / Actividades realizadas')
    respuesta_paciente = models.TextField(blank=True, verbose_name='Respuesta del paciente')
    recomendaciones = models.TextField(blank=True, verbose_name='Recomendaciones para el hogar')
    
    creado = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-fecha']
        verbose_name = 'Evaluación Fonoaudiológica'
        verbose_name_plural = 'Evaluaciones Fonoaudiológicas'
    
    def __str__(self):
        return f"Eval. {self.get_area_display()} - {self.fecha.strftime('%d/%m/%Y')}"                
    
class NotaClinica(models.Model):
    paciente = models.ForeignKey(
        'pacientes.Paciente', on_delete=models.CASCADE, related_name='notas_clinicas'
    )
    profesional = models.ForeignKey(
        'profesionales.Profesional', on_delete=models.SET_NULL, null=True, related_name='notas_clinicas'
    )
    fecha = models.DateField(default=date.today)
    titulo = models.CharField(max_length=200)
    tipo = models.CharField(max_length=30, choices=[
        ('observacion', 'Observación'), ('resultado', 'Resultado de estudio'),
        ('interconsulta', 'Interconsulta'), ('llamado', 'Llamado telefónico'),
        ('indicacion', 'Indicación'), ('otro', 'Otro'),
    ], default='observacion')
    contenido = models.TextField()
    archivo = models.FileField(upload_to='notas_clinicas/%Y/%m/', null=True, blank=True)
    creado = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-fecha', '-creado']
        verbose_name = 'Nota Clínica'
        verbose_name_plural = 'Notas Clínicas'
    
    def __str__(self):
        return f"{self.fecha.strftime('%d/%m/%Y')} - {self.titulo}"    


class SesionPsicologica(models.Model):
    TIPO_SESION = [
        ('primera', 'Primera consulta'),
        ('seguimiento', 'Seguimiento'),
        ('emergencia', 'Emergencia / Crisis'),
        ('evaluacion', 'Evaluación / Test'),
        ('cierre', 'Cierre / Alta'),
        ('otro', 'Otro'),
    ]
    
    paciente = models.ForeignKey(
        'pacientes.Paciente',
        on_delete=models.CASCADE,
        related_name='sesiones_psicologicas'
    )
    profesional = models.ForeignKey(
        'profesionales.Profesional',
        on_delete=models.SET_NULL,
        null=True,
        related_name='sesiones_psicologicas_realizadas'
    )
    fecha = models.DateField(default=date.today)
    tipo_sesion = models.CharField(max_length=20, choices=TIPO_SESION, default='seguimiento')
    motivo_consulta = models.TextField(blank=True, verbose_name='Motivo de consulta / Tema trabajado')
    notas_sesion = models.TextField(blank=True, verbose_name='Notas de la sesión')
    
    # Información clínica
    diagnostico = models.TextField(blank=True, verbose_name='Diagnóstico / Impresión diagnóstica')
    medicacion_psiquiatrica = models.TextField(blank=True, verbose_name='Medicación psiquiátrica actual')
    observaciones = models.TextField(blank=True)
    
    archivo = models.FileField(upload_to='sesiones_psicologicas/%Y/%m/', null=True, blank=True)
    creado = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-fecha', '-creado']
        verbose_name = 'Sesión Psicológica'
        verbose_name_plural = 'Sesiones Psicológicas'
    
    def __str__(self):
        return f"Sesión {self.fecha.strftime('%d/%m/%Y')} - {self.paciente.nombre_completo}"    


class ResultadoLaboratorio(models.Model):
    TIPOS_ESTUDIO = [
        ('sangre', 'Análisis de sangre'),
        ('orina', 'Análisis de orina'),
        ('heces', 'Análisis de heces'),
        ('cultivo', 'Cultivo'),
        ('biopsia', 'Biopsia'),
        ('serologia', 'Serología'),
        ('hormonas', 'Perfil hormonal'),
        ('imagenes', 'Diagnóstico por imágenes'),
        ('otro', 'Otro'),
    ]
    
    paciente = models.ForeignKey(
        'pacientes.Paciente',
        on_delete=models.CASCADE,
        related_name='resultados_laboratorio'
    )
    profesional = models.ForeignKey(
        'profesionales.Profesional',
        on_delete=models.SET_NULL,
        null=True,
        related_name='resultados_laboratorio_cargados'
    )
    fecha_estudio = models.DateField(verbose_name='Fecha del estudio')
    tipo_estudio = models.CharField(max_length=20, choices=TIPOS_ESTUDIO, default='sangre')
    nombre_estudio = models.CharField(max_length=200, verbose_name='Nombre del estudio')
    resultados = models.TextField(blank=True, verbose_name='Resultados (texto libre)')
    unidad = models.CharField(max_length=50, blank=True, verbose_name='Unidad')
    valores_referencia = models.TextField(blank=True, verbose_name='Valores de referencia')
    conclusion = models.TextField(blank=True, verbose_name='Conclusión')
    archivo = models.FileField(upload_to='resultados_laboratorio/%Y/%m/', null=True, blank=True)
    notas = models.TextField(blank=True, verbose_name='Notas adicionales')
    creado = models.DateTimeField(auto_now_add=True)
    metodo = models.CharField(max_length=200, blank=True, verbose_name='Método')
    
    class Meta:
        ordering = ['-fecha_estudio']
        verbose_name = 'Resultado de Laboratorio'
        verbose_name_plural = 'Resultados de Laboratorio'
    
    def __str__(self):
        return f"{self.nombre_estudio} - {self.paciente} ({self.fecha_estudio})"

class ParametroLaboratorio(models.Model):
    resultado = models.ForeignKey(
        'ResultadoLaboratorio',
        on_delete=models.CASCADE,
        related_name='parametros'
    )
    nombre = models.CharField(max_length=200, verbose_name='Parámetro')
    valor = models.CharField(max_length=100, verbose_name='Resultado')
    unidad = models.CharField(max_length=50, blank=True, verbose_name='Unidad')
    valor_referencia = models.CharField(max_length=100, blank=True, verbose_name='Valor de referencia')
    normal = models.BooleanField(default=True, verbose_name='¿Valor normal?')
    
    class Meta:
        verbose_name = 'Parámetro de Laboratorio'
        verbose_name_plural = 'Parámetros de Laboratorio'
        ordering = ['nombre']
    
    def __str__(self):
        return f"{self.nombre}: {self.valor} {self.unidad}"        
    

class Ejercicio(ModeloBase):
    profesional = models.ForeignKey(
        'profesionales.Profesional',
        on_delete=models.CASCADE,
        verbose_name='Profesional'
    )
    paciente = models.ForeignKey(
        'pacientes.Paciente',
        on_delete=models.CASCADE,
        related_name='ejercicios',
        verbose_name='Paciente'
    )
    fecha = models.DateField(default=date.today, verbose_name='Fecha')
    nombre = models.CharField(max_length=200, verbose_name='Nombre del ejercicio')
    series = models.PositiveIntegerField(default=3, verbose_name='Series')
    repeticiones = models.PositiveIntegerField(default=10, verbose_name='Repeticiones')
    descripcion = models.TextField(blank=True, verbose_name='Descripción / Notas')
    link_video = models.URLField(blank=True, verbose_name='Link de YouTube')

    class Meta:
        verbose_name = 'Ejercicio'
        verbose_name_plural = 'Ejercicios'
        ordering = ['-fecha', 'nombre']

    def __str__(self):
        return f"{self.nombre} ({self.series}x{self.repeticiones}) - {self.paciente.nombre_completo}"    

class ImagenEjercicio(ModeloBase):
    ejercicio = models.ForeignKey(
        Ejercicio,
        on_delete=models.CASCADE,
        related_name='imagenes',
        verbose_name='Ejercicio'
    )
    imagen = models.ImageField(upload_to='ejercicios/', verbose_name='Imagen')

    class Meta:
        verbose_name = 'Imagen de ejercicio'
        verbose_name_plural = 'Imágenes de ejercicios'

    def __str__(self):
        return f"Imagen de {self.ejercicio.nombre}"        


class PlanAlimentacion(ModeloBase):
    profesional = models.ForeignKey(
        'profesionales.Profesional',
        on_delete=models.CASCADE,
        verbose_name='Profesional'
    )
    paciente = models.ForeignKey(
        'pacientes.Paciente',
        on_delete=models.CASCADE,
        related_name='planes_alimentacion',
        verbose_name='Paciente'
    )
    fecha = models.DateField(default=date.today, verbose_name='Fecha')
    calorias_objetivo = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name='Calorías objetivo'
    )
    desayuno = models.TextField(blank=True, verbose_name='Desayuno')
    almuerzo = models.TextField(blank=True, verbose_name='Almuerzo')
    merienda = models.TextField(blank=True, verbose_name='Merienda')
    cena = models.TextField(blank=True, verbose_name='Cena')
    observaciones = models.TextField(blank=True, verbose_name='Observaciones')
    link_video = models.URLField(blank=True, verbose_name='Link de YouTube')

    class Meta:
        verbose_name = 'Plan de alimentación'
        verbose_name_plural = 'Planes de alimentación'
        ordering = ['-fecha']

    def __str__(self):
        return f"Plan de {self.paciente.nombre_completo} - {self.fecha}"


class ImagenPlanAlimentacion(ModeloBase):
    plan = models.ForeignKey(
        PlanAlimentacion,
        on_delete=models.CASCADE,
        related_name='imagenes',
        verbose_name='Plan de alimentación'
    )
    imagen = models.ImageField(upload_to='planes_alimentacion/', verbose_name='Imagen')

    class Meta:
        verbose_name = 'Imagen de plan de alimentación'
        verbose_name_plural = 'Imágenes de planes de alimentación'

    def __str__(self):
        return f"Imagen de {self.plan}"