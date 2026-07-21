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
    """Registro de consultas nutricionales con datos antropométricos."""
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
        'pacientes.Paciente',
        on_delete=models.CASCADE,
        related_name='consultas_nutricionales'
    )
    profesional = models.ForeignKey(
        'profesionales.Profesional',
        on_delete=models.SET_NULL,
        null=True,
        related_name='consultas_nutricionales_realizadas'
    )
    fecha = models.DateField(default=date.today)
    
    # Datos antropométricos
    peso_kg = models.DecimalField(max_digits=5, decimal_places=1, verbose_name='Peso (kg)')
    altura_cm = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True, verbose_name='Altura (cm)')
    imc = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True, verbose_name='IMC')
    perimetro_cintura_cm = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True, verbose_name='Cintura (cm)')
    porcentaje_grasa = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True, verbose_name='% Grasa corporal')
    porcentaje_musculo = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True, verbose_name='% Masa muscular')
    
    # Evaluación
    objetivo = models.CharField(max_length=30, choices=OBJETIVOS, blank=True)
    plan_nutricional = models.TextField(blank=True, verbose_name='Plan nutricional indicado')
    observaciones = models.TextField(blank=True)
    archivo = models.FileField(upload_to='tratamientos_odontologicos/%Y/%m/', null=True, blank=True)
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
    
    def save(self, *args, **kwargs):
        if not self.imc:
            self.imc = self.calcular_imc()
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