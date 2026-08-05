from datetime import date
from turnos_profesionales.models import TurnoProfesional
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from .models import EstudioMedico, Paciente, PacienteObraSocial
from usuarios.models import Usuario
import random, string
from django.core.paginator import Paginator
from profesionales.models import Profesional
from obras_sociales.models import ObraSocial, Plan
from historias_clinicas.models import ConsultaNutricional, EvaluacionFonoaudiologica, FichaTecnica, HistoriaClinica, Evolucion, NotaClinica, SesionPsicologica, TratamientoOdontologico
import unicodedata
import re
import random
import string



def generar_username(nombre, apellido, dni):
    """
    Genera un username limpio sin acentos, espacios ni caracteres especiales.
    Conserva la 'ñ'.
    Prioriza: inicial del nombre + apellido, o DNI como respaldo.
    """
    def limpiar_texto(texto):
        """Limpia acentos pero conserva la ñ."""
        texto = texto.lower().strip()
        # Reemplazar caracteres con acento por su versión sin acento
        reemplazos = {
            'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u', 'ü': 'u',
            'à': 'a', 'è': 'e', 'ì': 'i', 'ò': 'o', 'ù': 'u',
            'â': 'a', 'ê': 'e', 'î': 'i', 'ô': 'o', 'û': 'u',
            'ä': 'a', 'ë': 'e', 'ï': 'i', 'ö': 'o', 'ü': 'u',
            'ã': 'a', 'õ': 'o',
        }
        for acento, sin_acento in reemplazos.items():
            texto = texto.replace(acento, sin_acento)
        # Eliminar todo lo que no sea letra (a-z) o ñ
        # Conservamos: a-z y ñ
        texto = re.sub(r'[^a-zñ]', '', texto)
        return texto
    
    nombre_limpio = limpiar_texto(nombre)
    apellido_limpio = limpiar_texto(apellido)
    
    # Opción 1: inicial del nombre + apellido completo
    if nombre_limpio and apellido_limpio:
        username = f"{nombre_limpio[0]}{apellido_limpio}"
    elif apellido_limpio:
        username = apellido_limpio
    elif nombre_limpio:
        username = f"{nombre_limpio}{dni[-4:]}"
    else:
        username = f"paciente{dni}"
    
    return username


@login_required
def registrar_paciente(request):
    """El profesional registra un nuevo paciente."""
    if request.user.rol not in ['profesional', 'secretaria']:
        messages.error(request, 'No tenés acceso.')
        return redirect('home')
    
    if request.user.rol == 'secretaria':
        profesional = None
    elif request.user.rol == 'profesional':
        profesional = get_object_or_404(Profesional, usuario=request.user)
    else:
        profesional = None
    
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        apellido = request.POST.get('apellido', '').strip()
        dni = request.POST.get('dni', '').strip()
        fecha_nacimiento = request.POST.get('fecha_nacimiento')
        telefono = request.POST.get('telefono', '').strip()
        email = request.POST.get('email', '').strip()
        direccion = request.POST.get('direccion', '').strip()
        numero_afiliado = request.POST.get('numero_afiliado', '').strip()
        
        if not all([nombre, apellido, dni, fecha_nacimiento, telefono]):
            messages.error(request, 'Completá todos los campos obligatorios.')
            return redirect('registrar_paciente')
        
        if Paciente.objects.filter(dni=dni).exists():
            messages.error(request, 'Ya existe un paciente con ese DNI.')
            return redirect('registrar_paciente')
        
        paciente = Paciente.objects.create(
            nombre=nombre,
            apellido=apellido,
            dni=dni,
            fecha_nacimiento=fecha_nacimiento,
            telefono=telefono,
            email=email,
            direccion=direccion,
            numero_afiliado=numero_afiliado,
        )

        # Generar username limpio (sin acentos, conserva ñ)
        base_username = generar_username(nombre, apellido, dni)
        username = base_username
        
        # Si ya existe, agregar últimos 4 dígitos del DNI
        if Usuario.objects.filter(username=username).exists():
            username = f"{base_username}{dni[-4:]}"
        
        # Si todavía existe (muy raro), agregar número incremental
        contador = 1
        while Usuario.objects.filter(username=username).exists():
            username = f"{base_username}{dni[-4:]}{contador}"
            contador += 1

        # Contraseña: DNI sin puntos ni espacios
        password = dni.replace('.', '').replace(' ', '')

        usuario = Usuario.objects.create_user(
            username=username,
            password=password,
            first_name=nombre,
            last_name=apellido,
            email=email or '',
            rol='paciente',
            telefono=telefono
        )
        paciente.usuario = usuario
        paciente.save()

        messages.success(request, 
            f'✅ Paciente {paciente.nombre_completo} registrado correctamente.\n'
            f'🔑 Usuario: {username} | Contraseña: {password}\n'
            f'📋 Historia Clínica: HC-{paciente.id:06d}'
        )    
            
        # Crear historia clínica
        HistoriaClinica.objects.create(
            paciente=paciente,
            numero_historia=f"HC-{paciente.id:06d}"
        )
        return redirect('ficha_paciente', paciente_id=paciente.id)
    

    return render(request, 'pacientes/registrar.html', {
        'profesional': profesional,
    })

@login_required
def actualizar_sesiones(request, paciente_id):
    """Actualiza las sesiones de obra social desde la ficha."""
    if request.user.rol not in ['profesional', 'secretaria']:
        messages.error(request, 'No tenés acceso.')
        return redirect('home')
    
    paciente = get_object_or_404(Paciente, id=paciente_id)
    
    if request.method == 'POST':
        os_id = request.POST.get('os_id')
        sesiones_autorizadas = request.POST.get('sesiones_autorizadas')
        sesiones_restantes = request.POST.get('sesiones_restantes')
        fecha_vencimiento = request.POST.get('fecha_vencimiento')
        
        if os_id:
            os_paciente = get_object_or_404(PacienteObraSocial, id=os_id, paciente=paciente)
            os_paciente.sesiones_autorizadas = int(sesiones_autorizadas) if sesiones_autorizadas else None
            os_paciente.sesiones_restantes = int(sesiones_restantes) if sesiones_restantes else None
            os_paciente.fecha_vencimiento = fecha_vencimiento if fecha_vencimiento else None
            os_paciente.save()
            messages.success(request, '✅ Sesiones actualizadas correctamente.')
    
    return redirect('ficha_paciente', paciente_id=paciente.id)

@login_required
def buscar_paciente(request):
    """Buscar pacientes por nombre, apellido o DNI."""
    if request.user.rol not in ['profesional', 'secretaria']:
        messages.error(request, 'No tenés acceso.')
        return redirect('home')
    
    if request.user.rol == 'secretaria':
        profesional = None
        establecimiento = request.user.establecimiento
    elif request.user.rol == 'profesional':
        profesional = get_object_or_404(Profesional, usuario=request.user)
        # Agarrar el primer establecimiento donde atiende
        establecimiento = profesional.establecimientos.first()
    else:
        profesional = None
        establecimiento = None

    pacientes = []
    busqueda = ''
    
    if request.GET.get('q'):
        busqueda = request.GET.get('q')
        
        pacientes = Paciente.objects.filter(
            Q(nombre__icontains=busqueda) |
            Q(apellido__icontains=busqueda) |
            Q(dni__icontains=busqueda)
        )
        
        # Ambos (secretaria y profesional) filtran por el mismo consultorio
        if establecimiento:
            pacientes = pacientes.filter(
                turnoprofesional__establecimiento=establecimiento
            ).distinct()
        
        pacientes = pacientes[:20]
    
    return render(request, 'pacientes/buscar.html', {
        'profesional': profesional,
        'pacientes': pacientes,
        'busqueda': busqueda
    })
@login_required
def ficha_paciente(request, paciente_id):
    """Ficha completa del paciente con HC y turnos."""
    if request.user.rol not in ['profesional', 'secretaria']:
        messages.error(request, 'No tenés acceso.')
        return redirect('home')

    if request.user.rol == 'secretaria':
        profesional = None
        establecimiento = request.user.establecimiento
        # La secretaria siempre ve los turnos de su único consultorio → no mostrar columna consultorio
        mostrar_consultorio = False
        mostrar_profesional = True   # porque puede haber varios profesionales en el consultorio
    elif request.user.rol == 'profesional':
        profesional = get_object_or_404(Profesional, usuario=request.user)
        establecimiento = None
        # Mostrar consultorio solo si el profesional atiende en más de un lugar
        mostrar_consultorio = profesional.establecimientos.count() > 1
        mostrar_profesional = False  # el profesional ve sus propios turnos, no necesita ver su nombre
    else:
        profesional = None
        establecimiento = None
        mostrar_consultorio = False
        mostrar_profesional = False

    paciente = get_object_or_404(Paciente, id=paciente_id)
    hoy = date.today()

    historia = HistoriaClinica.objects.filter(paciente=paciente).first()
    evoluciones = Evolucion.objects.filter(
        historia_clinica=historia
    ).order_by('-creado') if historia else []

    # Próximos turnos
    if request.user.rol == 'secretaria':
        proximos_turnos = TurnoProfesional.objects.filter(
            paciente=paciente,
            fecha__gte=hoy,
            estado__in=['pendiente', 'confirmado'],
            establecimiento=establecimiento
        ).order_by('fecha', 'hora_inicio')
    elif request.user.rol == 'profesional':
        proximos_turnos = TurnoProfesional.objects.filter(
            profesional=profesional,
            paciente=paciente,
            fecha__gte=hoy,
            estado__in=['pendiente', 'confirmado']
        ).order_by('fecha', 'hora_inicio')
    else:
        proximos_turnos = []

    # Turnos pasados
    if request.user.rol == 'secretaria':
        turnos_pasados = TurnoProfesional.objects.filter(
            paciente=paciente,
            estado__in=['completado', 'cancelado', 'no_asistio'],
            establecimiento=establecimiento
        ).order_by('-fecha', '-hora_inicio')[:20]
    elif request.user.rol == 'profesional':
        turnos_pasados = TurnoProfesional.objects.filter(
            profesional=profesional,
            paciente=paciente,
            estado__in=['completado', 'cancelado', 'no_asistio']
        ).order_by('-fecha', '-hora_inicio')[:20]
    else:
        turnos_pasados = []

    # Paginación de próximos turnos
    prox_page = request.GET.get('prox_page', 1)
    paginator_prox = Paginator(proximos_turnos, 5   )  # 5 por página
    try:
        proximos_turnos_paginados = paginator_prox.page(prox_page)
    except:
        proximos_turnos_paginados = paginator_prox.page(1)

    # Paginación del historial (turnos pasados)
    hist_page = request.GET.get('hist_page', 1)
    paginator_hist = Paginator(turnos_pasados, 10)
    try:
        turnos_pasados_paginados = paginator_hist.page(hist_page)
    except:
        turnos_pasados_paginados = paginator_hist.page(1)        

    # Filtrar OS: solo las del profesional logueado (o todas si es secretaria)
    if request.user.rol == 'profesional' and profesional:
        obras_sociales_paciente = paciente.mis_obras_sociales.filter(
            profesional=profesional
        )
    elif request.user.rol == 'secretaria':
        obras_sociales_paciente = paciente.mis_obras_sociales.all()
    else:
        obras_sociales_paciente = paciente.mis_obras_sociales.none()

    # Detectar si viene de cargar evolución (para mostrar botón de pago)
    turno_para_pagar = None
    turno_id = request.GET.get('turno_id')
    if turno_id:
        try:
            turno_para_pagar = TurnoProfesional.objects.get(id=turno_id)
        except TurnoProfesional.DoesNotExist:
            pass

    return render(request, 'pacientes/ficha.html', {
        'profesional': profesional,
        'paciente': paciente,
        'historia': historia,
        'evoluciones': evoluciones,
        'proximos_turnos': proximos_turnos,
        'turnos': turnos_pasados,
        'obras_sociales_paciente': obras_sociales_paciente,
        'hoy': hoy,
        'es_secretaria': request.user.rol == 'secretaria',
        'turno_para_pagar': turno_para_pagar,
        'mostrar_consultorio': mostrar_consultorio,
        'mostrar_profesional': mostrar_profesional,
        'proximos_turnos': proximos_turnos_paginados,
        'turnos': turnos_pasados_paginados,
        'mostrar_consultorio': mostrar_consultorio,
        'mostrar_profesional': mostrar_profesional,
    })

@login_required
def editar_paciente(request, paciente_id):
    """Editar datos del paciente."""
    if request.user.rol not in ['profesional', 'secretaria']:
        messages.error(request, 'No tenés acceso.')
        return redirect('home')
    
    if request.user.rol == 'secretaria':
        profesional = None
    elif request.user.rol == 'profesional':
        profesional = get_object_or_404(Profesional, usuario=request.user)
    else:
        profesional = None
    paciente = get_object_or_404(Paciente, id=paciente_id)
    historia = HistoriaClinica.objects.filter(paciente=paciente).first()
    
    if request.method == 'POST':
        paciente.nombre = request.POST.get('nombre', paciente.nombre)
        paciente.apellido = request.POST.get('apellido', paciente.apellido)
        paciente.dni = request.POST.get('dni', paciente.dni)
        paciente.fecha_nacimiento = request.POST.get('fecha_nacimiento', paciente.fecha_nacimiento)
        paciente.telefono = request.POST.get('telefono', paciente.telefono)
        paciente.email = request.POST.get('email', paciente.email)
        paciente.direccion = request.POST.get('direccion', paciente.direccion)
        paciente.numero_afiliado = request.POST.get('numero_afiliado', paciente.numero_afiliado)

        paciente.save()
        
        # Actualizar historia clínica si existe
        if historia:
            historia.antecedentes_personales = request.POST.get('antecedentes_personales', historia.antecedentes_personales)
            historia.antecedentes_familiares = request.POST.get('antecedentes_familiares', historia.antecedentes_familiares)
            historia.alergias = request.POST.get('alergias', historia.alergias)
            historia.medicacion_habitual = request.POST.get('medicacion_habitual', historia.medicacion_habitual)
            historia.save()
        
        messages.success(request, f'Datos de {paciente.nombre_completo} actualizados.')
        return redirect('ficha_paciente', paciente_id=paciente.id)
    
    obras_sociales = ObraSocial.objects.filter(activo=True)
    
    return render(request, 'pacientes/editar.html', {
        'profesional': profesional,
        'paciente': paciente,
        'historia': historia,
        'obras_sociales': obras_sociales
    })




# Agregá al final de pacientes/views.py

@login_required
def ficha_tecnica(request, paciente_id):
    if request.user.rol not in ['profesional', 'secretaria']:
        messages.error(request, 'No tenés acceso.')
        return redirect('home')
    
    paciente = get_object_or_404(Paciente, id=paciente_id)
    
    if request.user.rol == 'profesional':
        profesional = get_object_or_404(Profesional, usuario=request.user)
    else:
        profesional = Profesional.objects.first()
    
    ficha_tecnica, created = FichaTecnica.objects.get_or_create(
        paciente=paciente,
        defaults={
            'profesional': profesional,
            'especialidad': profesional.especialidad if profesional else 'general'
        }
    )
    
    templates_por_especialidad = {
    'odontologia': 'pacientes/fichas_especialidades/odontologia.html',
    'kinesiologia': 'pacientes/fichas_especialidades/kinesiologia.html',
    'nutricion': 'pacientes/fichas_especialidades/nutricion.html',    
    'fonoaudiologia': 'pacientes/fichas_especialidades/fonoaudiologia.html',  
    'psicologia': 'pacientes/fichas_especialidades/psicologia.html',
    }
    
    especialidad = profesional.especialidad if profesional else 'general'
    template = templates_por_especialidad.get(
        especialidad, 
        'pacientes/fichas_especialidades/default.html'
    )
    
    if request.method == 'POST':
        datos = {}
        for key, value in request.POST.items():
            if key not in ['csrfmiddlewaretoken', 'notas_generales']:
                datos[key] = value
        
        ficha_tecnica.datos_especificos = datos
        ficha_tecnica.notas_generales = request.POST.get('notas_generales', '')
        ficha_tecnica.save()
        
        # Kinesiología
        if especialidad == 'kinesiologia':
            zona = request.POST.get('nueva_lesion_zona', '').strip()
            fecha_lesion = request.POST.get('nueva_lesion_fecha', '').strip()
            if zona and fecha_lesion:
                lesion = Lesion.objects.create(
                    paciente=paciente,
                    fecha_lesion=fecha_lesion,
                    tipo_lesion=request.POST.get('nueva_lesion_tipo', 'otra'),
                    zona=zona,
                    descripcion=request.POST.get('nueva_lesion_descripcion', ''),
                    tratamiento=request.POST.get('nueva_lesion_tratamiento', ''),
                )
                archivo = request.FILES.get('nota_archivo')
                if archivo:
                    lesion.archivo = archivo
                    lesion.save()
        
        # Nutrición
        elif especialidad == 'nutricion':
            peso = request.POST.get('peso_kg', '').strip()
            if peso:
                tipo_consulta = request.POST.get('tipo_consulta', 'inicial')
                consulta_base = None
                es_seguimiento = False

                if tipo_consulta == 'seguimiento':
                    es_seguimiento = True
                    consulta_base = ConsultaNutricional.objects.filter(
                        paciente=paciente, es_seguimiento=False
                    ).order_by('-fecha').first()

                consulta = ConsultaNutricional.objects.create(
                    paciente=paciente, profesional=profesional,
                    fecha=request.POST.get('fecha', date.today()),
                    peso_kg=peso,
                    altura_cm=request.POST.get('altura_cm') or None,
                    imc=request.POST.get('imc') or None,
                    perimetro_cintura_cm=request.POST.get('perimetro_cintura_cm') or None,
                    perimetro_cadera_cm=request.POST.get('perimetro_cadera_cm') or None,
                    icc=request.POST.get('icc') or None,
                    porcentaje_grasa=request.POST.get('porcentaje_grasa') or None,
                    porcentaje_musculo=request.POST.get('porcentaje_musculo') or None,
                    peso_inicial_kg=request.POST.get('peso_inicial_kg') or None,
                    objetivo=request.POST.get('objetivo', ''),
                    expectativas_metas=request.POST.get('expectativas_metas', ''),
                    plan_nutricional=request.POST.get('plan_nutricional', ''),
                    medicacion_suplementos=request.POST.get('medicacion_suplementos', ''),
                    laboratorios=request.POST.get('laboratorios', ''),
                    observaciones=request.POST.get('observaciones_nutricion', ''),
                    es_seguimiento=es_seguimiento,
                    consulta_base=consulta_base,
                )
                archivo = request.FILES.get('nota_archivo')
                if archivo:
                    consulta.archivo = archivo
                    consulta.save()
        
        # Fonoaudiología
        elif especialidad == 'fonoaudiologia':
            area = request.POST.get('area', '').strip()
            if area:
                evaluacion = EvaluacionFonoaudiologica.objects.create(
                    paciente=paciente, profesional=profesional,
                    fecha=request.POST.get('fecha', date.today()),
                    area=area,
                    diagnostico=request.POST.get('diagnostico', ''),
                    evaluacion=request.POST.get('evaluacion', ''),
                    objetivos=request.POST.get('objetivos', ''),
                    ejercicios=request.POST.get('ejercicios', ''),
                    respuesta_paciente=request.POST.get('respuesta_paciente', ''),
                    recomendaciones=request.POST.get('recomendaciones', ''),
                )
                archivo = request.FILES.get('nota_archivo')
                if archivo:
                    evaluacion.archivo = archivo
                    evaluacion.save()

        elif especialidad == 'psicologia':
            if request.method == 'POST':
                fecha = request.POST.get('fecha', date.today())
                tipo = request.POST.get('tipo_sesion', 'seguimiento')
                motivo = request.POST.get('motivo_consulta', '')
                notas = request.POST.get('notas_sesion', '')
                diagnostico = request.POST.get('diagnostico', '')
                medicacion = request.POST.get('medicacion_psiquiatrica', '')
                observaciones = request.POST.get('observaciones', '')

                sesion = SesionPsicologica.objects.create(
                    paciente=paciente,
                    profesional=profesional,
                    fecha=fecha,
                    tipo_sesion=tipo,
                    motivo_consulta=motivo,
                    notas_sesion=notas,
                    diagnostico=diagnostico,
                    medicacion_psiquiatrica=medicacion,
                    observaciones=observaciones,
                )
                archivo = request.FILES.get('nota_archivo')
                if archivo:
                    sesion.archivo = archivo
                    sesion.save()            
        
        # Odontología
        elif especialidad == 'odontologia':
            pieza = request.POST.get('nuevo_tratamiento_pieza', '').strip()
            tipo = request.POST.get('nuevo_tratamiento_tipo', '').strip()
            fecha_trat = request.POST.get('nuevo_tratamiento_fecha', '').strip()
            if pieza and tipo:
                tratamiento = TratamientoOdontologico.objects.create(
                    paciente=paciente, profesional=profesional,
                    fecha=fecha_trat or date.today(),
                    pieza_dental=pieza, tipo_tratamiento=tipo,
                    material_usado=request.POST.get('nuevo_tratamiento_material', ''),
                    descripcion=request.POST.get('nuevo_tratamiento_descripcion', ''),
                    costo=request.POST.get('nuevo_tratamiento_costo') or None,
                    fecha_proximo_control=request.POST.get('nuevo_tratamiento_control') or None,
                )
                archivo = request.FILES.get('nota_archivo')
                if archivo:
                    tratamiento.archivo = archivo
                    tratamiento.save()
        
        # Nota clínica (todas las especialidades)
        titulo_nota = request.POST.get('nota_titulo', '').strip()
        contenido_nota = request.POST.get('nota_contenido', '').strip()
        if titulo_nota and contenido_nota:
            nota = NotaClinica.objects.create(
                paciente=paciente, 
                profesional=profesional,
                fecha=request.POST.get('nota_fecha', date.today()),
                tipo=request.POST.get('nota_tipo', 'observacion'),
                titulo=titulo_nota,
                contenido=contenido_nota,                
            )
            archivo = request.FILES.get('nota_archivo')
            if archivo:
                nota.archivo = archivo
                nota.save()
        
        messages.success(request, '✅ Ficha guardada correctamente.')
        return redirect('ficha_tecnica', paciente_id=paciente.id)

    
    context = {
        'paciente': paciente,
        'ficha_tecnica': ficha_tecnica,
        'profesional': profesional,
        'hoy': date.today(),
        'notas': paciente.notas_clinicas.all(),
        'sesiones': paciente.sesiones_psicologicas.all() if especialidad == 'psicologia' else None,
    }

    # Contexto específico según especialidad
    if especialidad == 'nutricion':
        consultas = paciente.consultas_nutricionales.all()
        context['consultas'] = consultas
        context['especialidad'] = 'nutricion'
        
        # Calcular tendencia y peso máximo para el gráfico
        if consultas.count() >= 2:
            primer_peso = consultas.last().peso_kg
            ultimo_peso = consultas.first().peso_kg
            if primer_peso and ultimo_peso:
                cambio_peso = ultimo_peso - primer_peso
                context['cambio_peso'] = cambio_peso
                context['tendencia_peso'] = abs(cambio_peso)
            pesos = [c.peso_kg for c in consultas if c.peso_kg]
            if pesos:
                context['peso_max'] = max(pesos)
        else:
            context['peso_max'] = 100  # valor por defecto

    elif especialidad == 'fonoaudiologia':
        context['evaluaciones'] = paciente.evaluaciones_fonoaudiologicas.all()
        context['especialidad'] = 'fonoaudiologia'

    
    return render(request, template, context)

@login_required
def estudios_paciente(request, paciente_id):
    """Ver y subir estudios de un paciente (vista profesional/secretaria)."""
    if request.user.rol not in ['profesional', 'secretaria']:
        messages.error(request, 'No tenés acceso.')
        return redirect('home')
    
    paciente = get_object_or_404(Paciente, id=paciente_id)
    
    # Determinar profesional según el rol
    if request.user.rol == 'secretaria':
        profesional = None   # la secretaria puede ver todos los estudios del paciente
    elif request.user.rol == 'profesional':
        profesional = get_object_or_404(Profesional, usuario=request.user)
    else:
        profesional = None
    
    # Subida de archivo (POST)
    if request.method == 'POST':
        titulo = request.POST.get('titulo', '').strip()
        descripcion = request.POST.get('descripcion', '')
        tipo_estudio = request.POST.get('tipo_estudio', 'otro')
        fecha_estudio = request.POST.get('fecha_estudio') or None
        archivo = request.FILES.get('archivo')
        
        if not titulo or not archivo:
            messages.error(request, 'El título y el archivo son obligatorios.')
            return redirect('estudios_paciente', paciente_id=paciente.id)
        
        # La secretaria podría elegir un profesional o dejarlo sin asignar; 
        # para simplificar, si es secretaria, profesional = None (aunque puede seleccionarse si se desea).
        EstudioMedico.objects.create(
            paciente=paciente,
            profesional=profesional,   # None para secretaria, o el profesional logueado
            titulo=titulo,
            descripcion=descripcion,
            tipo_estudio=tipo_estudio,
            fecha_estudio=fecha_estudio,
            archivo=archivo,
            subido_por='profesional',  # siempre será subido por el profesional en esta vista
        )
        
        messages.success(request, f'Estudio "{titulo}" subido correctamente.')
        return redirect('estudios_paciente', paciente_id=paciente.id)
    
    # GET – Mostrar estudios
    estudios = paciente.estudios_medicos.all()
    
    # Filtrar según privacidad
    if profesional:   # si es un profesional, solo ve los estudios que le corresponden
        estudios = estudios.filter(
            Q(profesional=profesional) |      # estudios que él subió
            Q(subido_por='paciente', profesional=profesional)   # estudios que el paciente le envió a él
        )
    # Si es secretaria, ve todos los estudios del paciente (sin filtro adicional)

    return render(request, 'pacientes/estudios.html', {
        'paciente': paciente,
        'estudios': estudios,
        'tipos_estudio': EstudioMedico._meta.get_field('tipo_estudio').choices,
        'profesional': profesional,
        'es_secretaria': request.user.rol == 'secretaria',
    })

from historias_clinicas.models import Lesion
from datetime import date

@login_required
def agregar_lesion(request, paciente_id):
    """Agrega una lesión al historial del paciente."""
    if request.user.rol not in ['profesional', 'secretaria']:
        return redirect('home')
    
    paciente = get_object_or_404(Paciente, id=paciente_id)
    
    if request.method == 'POST':
        Lesion.objects.create(
            paciente=paciente,
            fecha_lesion=request.POST.get('fecha_lesion', date.today()),
            tipo_lesion=request.POST.get('tipo_lesion', 'otra'),
            zona=request.POST.get('zona', ''),
            descripcion=request.POST.get('descripcion', ''),
            tratamiento=request.POST.get('tratamiento', ''),
        )
        messages.success(request, 'Lesión registrada correctamente.')
    
    return redirect('ficha_tecnica', paciente_id=paciente.id)


@login_required
def marcar_lesion_resuelta(request, lesion_id):
    """Marca una lesión como resuelta."""
    if request.user.rol not in ['profesional', 'secretaria']:
        return redirect('home')
    
    lesion = get_object_or_404(Lesion, id=lesion_id)
    lesion.resuelta = True
    lesion.fecha_resolucion = date.today()
    lesion.save()
    
    messages.success(request, 'Lesión marcada como resuelta.')
    return redirect('ficha_tecnica', paciente_id=lesion.paciente.id)


@login_required
def eliminar_lesion(request, lesion_id):
    """Elimina una lesión del historial."""
    if request.user.rol not in ['profesional', 'secretaria']:
        return redirect('home')
    
    lesion = get_object_or_404(Lesion, id=lesion_id)
    paciente_id = lesion.paciente.id
    lesion.delete()
    
    messages.success(request, 'Lesión eliminada del historial.')
    return redirect('ficha_tecnica', paciente_id=paciente_id)


from historias_clinicas.models import Lesion

@login_required
def marcar_lesion_resuelta(request, lesion_id):
    if request.user.rol not in ['profesional', 'secretaria']:
        return redirect('home')
    
    lesion = get_object_or_404(Lesion, id=lesion_id)
    lesion.resuelta = True
    lesion.fecha_resolucion = date.today()
    lesion.save()
    messages.success(request, '✅ Lesión marcada como resuelta.')
    return redirect('ficha_tecnica', paciente_id=lesion.paciente.id)


@login_required
def eliminar_lesion(request, lesion_id):
    if request.user.rol not in ['profesional', 'secretaria']:
        return redirect('home')
    
    lesion = get_object_or_404(Lesion, id=lesion_id)
    paciente_id = lesion.paciente.id
    lesion.delete()
    messages.success(request, '🗑️ Lesión eliminada del historial.')
    return redirect('ficha_tecnica', paciente_id=paciente_id)   


from historias_clinicas.models import Lesion, SeguimientoTratamiento

@login_required
def seguimiento_lesion(request, lesion_id):
    """Pantalla de seguimiento de una lesión específica."""
    if request.user.rol not in ['profesional', 'secretaria']:
        return redirect('home')
    
    lesion = get_object_or_404(Lesion, id=lesion_id)
    seguimientos = lesion.seguimientos.all()
    
    return render(request, 'pacientes/fichas_especialidades/seguimiento_lesion.html', {
        'lesion': lesion,
        'paciente': lesion.paciente,
        'seguimientos': seguimientos,
    })


@login_required
def agregar_seguimiento(request, lesion_id):
    """Agrega un registro de progreso a una lesión."""
    if request.user.rol not in ['profesional', 'secretaria']:
        return redirect('home')
    
    lesion = get_object_or_404(Lesion, id=lesion_id)
    
    if request.method == 'POST':
        SeguimientoTratamiento.objects.create(
            paciente=lesion.paciente,
            lesion=lesion,
            fecha=request.POST.get('fecha'),
            peso_trabajo_kg=request.POST.get('peso_trabajo_kg') or None,
            series=request.POST.get('series') or None,
            repeticiones=request.POST.get('repeticiones') or None,
            nivel_dolor=request.POST.get('nivel_dolor') or None,
            rango_movimiento=request.POST.get('rango_movimiento', ''),
            ejercicios_realizados=request.POST.get('ejercicios_realizados', ''),
            observaciones=request.POST.get('observaciones', ''),
        )
        messages.success(request, '✅ Progreso registrado.')
    
    return redirect('seguimiento_lesion', lesion_id=lesion.id)


@login_required
def limpiar_seguimientos(request, lesion_id):
    """Limpia todo el historial de seguimiento de una lesión."""
    if request.user.rol not in ['profesional', 'secretaria']:
        return redirect('home')
    
    lesion = get_object_or_404(Lesion, id=lesion_id)
    lesion.seguimientos.all().delete()
    messages.success(request, '🧹 Historial limpiado.')
    return redirect('seguimiento_lesion', lesion_id=lesion.id)


@login_required
def eliminar_seguimiento(request, seguimiento_id):
    """Elimina un registro de seguimiento."""
    if request.user.rol not in ['profesional', 'secretaria']:
        return redirect('home')
    
    seguimiento = get_object_or_404(SeguimientoTratamiento, id=seguimiento_id)
    lesion_id = seguimiento.lesion.id
    seguimiento.delete()
    messages.success(request, '🗑️ Registro eliminado.')
    return redirect('seguimiento_lesion', lesion_id=lesion_id)


@login_required
def eliminar_tratamiento_odontologico(request, tratamiento_id):
    if request.user.rol not in ['profesional', 'secretaria']:
        return redirect('home')
    
    tratamiento = get_object_or_404(TratamientoOdontologico, id=tratamiento_id)
    paciente_id = tratamiento.paciente.id
    tratamiento.delete()
    messages.success(request, '🗑️ Tratamiento eliminado.')
    return redirect('ficha_tecnica', paciente_id=paciente_id)

@login_required
def eliminar_consulta_nutricional(request, consulta_id):
    if request.user.rol not in ['profesional', 'secretaria']:
        return redirect('home')
    consulta = get_object_or_404(ConsultaNutricional, id=consulta_id)
    paciente_id = consulta.paciente.id
    consulta.delete()
    messages.success(request, '🗑️ Consulta eliminada.')
    return redirect('ficha_tecnica', paciente_id=paciente_id)

@login_required
def eliminar_evaluacion_fono(request, evaluacion_id):
    if request.user.rol not in ['profesional', 'secretaria']:
        return redirect('home')
    evaluacion = get_object_or_404(EvaluacionFonoaudiologica, id=evaluacion_id)
    paciente_id = evaluacion.paciente.id
    evaluacion.delete()
    messages.success(request, '🗑️ Evaluación eliminada.')
    return redirect('ficha_tecnica', paciente_id=paciente_id)

@login_required
def eliminar_nota_clinica(request, nota_id):
    if request.user.rol not in ['profesional', 'secretaria']:
        return redirect('home')
    nota = get_object_or_404(NotaClinica, id=nota_id)
    paciente_id = nota.paciente.id
    nota.delete()
    messages.success(request, '🗑️ Nota eliminada.')
    return redirect('ficha_tecnica', paciente_id=paciente_id)

@login_required
def gestionar_obras_sociales(request, paciente_id):
    """Pantalla para gestionar obras sociales y sesiones del paciente."""
    if request.user.rol not in ['profesional', 'secretaria']:
        messages.error(request, 'No tenés acceso.')
        return redirect('home')
    
    paciente = get_object_or_404(Paciente, id=paciente_id)
    
    if request.user.rol == 'profesional':
        profesional = get_object_or_404(Profesional, usuario=request.user)
    else:
        profesional = None
    
    # Filtrar OS disponibles: solo las que acepta el profesional
    if profesional:
        obras_sociales_disponibles = profesional.obras_sociales.filter(activo=True)
    else:
        obras_sociales_disponibles = ObraSocial.objects.filter(activo=True)
    
    # Filtrar OS del paciente por profesional
    if profesional:
        obras_sociales_paciente = paciente.mis_obras_sociales.filter(profesional=profesional)
    else:
        obras_sociales_paciente = paciente.mis_obras_sociales.all()
    
    if request.method == 'POST':
        accion = request.POST.get('accion', '')
        
        # Guardar sesiones
        if accion == 'guardar_sesiones':
            os_id = request.POST.get('os_id')
            sesiones_autorizadas = request.POST.get('sesiones_autorizadas')
            sesiones_restantes = request.POST.get('sesiones_restantes')
            fecha_vencimiento = request.POST.get('fecha_vencimiento')
            
            if os_id:
                os_paciente = get_object_or_404(PacienteObraSocial, id=os_id, paciente=paciente)
                os_paciente.sesiones_autorizadas = int(sesiones_autorizadas) if sesiones_autorizadas else None
                os_paciente.sesiones_restantes = int(sesiones_restantes) if sesiones_restantes else None
                os_paciente.fecha_vencimiento = fecha_vencimiento if fecha_vencimiento else None
                os_paciente.save()
                messages.success(request, '✅ Sesiones actualizadas.')
        
        elif accion == 'agregar_obra_social':
            obra_social_id = request.POST.get('obra_social')
            plan_id = request.POST.get('plan')
            numero_afiliado = request.POST.get('numero_afiliado', '')
            
            if obra_social_id:
                obra_social = ObraSocial.objects.get(id=obra_social_id)
                
                # Buscar si ya existe esta OS para el paciente (heredar datos)
                os_existente = PacienteObraSocial.objects.filter(
                    paciente=paciente,
                    obra_social_id=obra_social_id
                ).first()
                
                # Heredar nº afiliado y plan si no se especificaron
                numero_afiliado_final = numero_afiliado or (os_existente.numero_afiliado if os_existente else '')
                plan_final_id = plan_id or (os_existente.plan_id if os_existente else None)
                plan_final = Plan.objects.get(id=plan_final_id) if plan_final_id else None
                
                # Crear la OS para el profesional actual
                PacienteObraSocial.objects.get_or_create(
                    paciente=paciente,
                    obra_social=obra_social,
                    profesional=profesional,
                    defaults={
                        'plan': plan_final,
                        'numero_afiliado': numero_afiliado_final,
                        'activa': True,
                    }
                )
                
                # Crear automáticamente para otros profesionales que aceptan esta OS
                otros_profesionales = Profesional.objects.filter(
                    obras_sociales=obra_social,
                    establecimientos__in=profesional.establecimientos.all()
                ).exclude(id=profesional.id).distinct()
                
                for otro_prof in otros_profesionales:
                    PacienteObraSocial.objects.get_or_create(
                        paciente=paciente,
                        obra_social=obra_social,
                        profesional=otro_prof,
                        defaults={
                            'plan': plan_final,
                            'numero_afiliado': numero_afiliado_final,
                            'activa': True,
                        }
                    )
                    print(f"  ✅ OS creada para {otro_prof.nombre_completo}")
                
                # Actualizar campo legacy
                paciente.obra_social = obra_social
                paciente.numero_afiliado = numero_afiliado_final
                if plan_final_id:
                    paciente.plan_obra_social_id = plan_final_id
                paciente.save()
                
                messages.success(request, '✅ Obra social agregada correctamente.')
        
        # Activar/Desactivar obra social
        elif accion == 'toggle_obra_social':
            os_id = request.POST.get('os_id')
            obra_social_paciente = get_object_or_404(PacienteObraSocial, id=os_id, paciente=paciente)
            obra_social_paciente.activa = not obra_social_paciente.activa
            obra_social_paciente.save()
            estado = "activada" if obra_social_paciente.activa else "desactivada"
            messages.success(request, f'✅ Obra social {estado}.')
        
        # Eliminar obra social
        elif accion == 'eliminar_obra_social':
            os_id = request.POST.get('os_id')
            obra_social_paciente = get_object_or_404(PacienteObraSocial, id=os_id, paciente=paciente)
            obra_social_paciente.delete()
            messages.success(request, '🗑️ Obra social eliminada.')
        
        return redirect('gestionar_obras_sociales', paciente_id=paciente.id)
    
    context = {
        'paciente': paciente,
        'profesional': profesional,
        'obras_sociales_disponibles': obras_sociales_disponibles,
        'hoy': date.today(),
        'es_secretaria': request.user.rol == 'secretaria',
        'obras_sociales_paciente': obras_sociales_paciente,
    }
    
    return render(request, 'pacientes/gestionar_obras_sociales.html', context)