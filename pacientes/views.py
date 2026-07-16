from datetime import date
from turnos_profesionales.models import TurnoProfesional
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from .models import EstudioMedico, Paciente, PacienteObraSocial
from usuarios.models import Usuario
import random, string
from profesionales.models import Profesional
from obras_sociales.models import ObraSocial, Plan
from historias_clinicas.models import ConsultaNutricional, EvaluacionFonoaudiologica, FichaTecnica, HistoriaClinica, Evolucion, NotaClinica, TratamientoOdontologico



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
        nombre = request.POST.get('nombre')
        apellido = request.POST.get('apellido')
        dni = request.POST.get('dni')
        fecha_nacimiento = request.POST.get('fecha_nacimiento')
        telefono = request.POST.get('telefono')
        email = request.POST.get('email', '')
        direccion = request.POST.get('direccion', '')
        numero_afiliado = request.POST.get('numero_afiliado', '')
        
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


        # Generar username único
        base_username = f"{nombre.lower()}.{apellido.lower()}".replace(" ", "")
        username = base_username
        if Usuario.objects.filter(username=username).exists():
            username = f"{base_username}{random.randint(1,999)}"

        # Generar contraseña: DNI si existe, si no una aleatoria
        password = dni if dni else ''.join(random.choices(string.digits, k=6))

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
            f'Paciente {paciente.nombre_completo} registrado correctamente.\n'
            f'🔑 Usuario: {username} | Contraseña: {password}'
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
        sesiones_autorizadas = request.POST.get('sesiones_autorizadas')
        sesiones_restantes = request.POST.get('sesiones_restantes')
        fecha_vencimiento = request.POST.get('fecha_vencimiento')
        
        paciente.sesiones_autorizadas = int(sesiones_autorizadas) if sesiones_autorizadas else None
        paciente.sesiones_restantes = int(sesiones_restantes) if sesiones_restantes else None
        paciente.fecha_vencimiento_sesiones = fecha_vencimiento if fecha_vencimiento else None
        paciente.save()
        
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
    elif request.user.rol == 'profesional':
        profesional = get_object_or_404(Profesional, usuario=request.user)
    else:
        profesional = None  


    pacientes = []
    busqueda = ''
    
    if request.GET.get('q'):
        busqueda = request.GET.get('q')
        pacientes = Paciente.objects.filter(
            Q(nombre__icontains=busqueda) |
            Q(apellido__icontains=busqueda) |
            Q(dni__icontains=busqueda)
        )[:20]
    
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
    elif request.user.rol == 'profesional':
        profesional = get_object_or_404(Profesional, usuario=request.user)
        establecimiento = None
    else:
        profesional = None
        establecimiento = None

    paciente = get_object_or_404(Paciente, id=paciente_id)
    hoy = date.today()
    
    historia = HistoriaClinica.objects.filter(paciente=paciente).first()
    evoluciones = Evolucion.objects.filter(
        historia_clinica=historia
    ).order_by('-creado') if historia else []
    
    # Próximos turnos
    if request.user.rol == 'secretaria':
        # Secretaria solo ve turnos de SU consultorio
        proximos_turnos = TurnoProfesional.objects.filter(
            paciente=paciente,
            fecha__gte=hoy,
            estado__in=['pendiente', 'confirmado'],
            establecimiento=establecimiento
        ).order_by('fecha', 'hora_inicio')
    elif request.user.rol == 'profesional':
        # Profesional solo ve SUS propios turnos con este paciente
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
    
    return render(request, 'pacientes/ficha.html', {
        'profesional': profesional,
        'paciente': paciente,
        'historia': historia,
        'evoluciones': evoluciones,
        'proximos_turnos': proximos_turnos,
        'turnos': turnos_pasados,
        'hoy': hoy,
        'es_secretaria': request.user.rol == 'secretaria'
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
        paciente.sesiones_autorizadas = request.POST.get('sesiones_autorizadas') or None
        if paciente.sesiones_autorizadas:
            paciente.sesiones_autorizadas = int(paciente.sesiones_autorizadas)

        paciente.sesiones_restantes = request.POST.get('sesiones_restantes') or None
        if paciente.sesiones_restantes:
            paciente.sesiones_restantes = int(paciente.sesiones_restantes)

        paciente.fecha_vencimiento_sesiones = request.POST.get('fecha_vencimiento') or None
            
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
    }
    
    especialidad = profesional.especialidad if profesional else 'general'
    template = templates_por_especialidad.get(
        especialidad, 
        'pacientes/fichas_especialidades/default.html'
    )
    
    if request.method == 'POST':
        # Guardar datos en el JSON de la ficha
        datos = {}
        for key, value in request.POST.items():
            if key not in ['csrfmiddlewaretoken', 'notas_generales']:
                datos[key] = value
        
        ficha_tecnica.datos_especificos = datos
        ficha_tecnica.notas_generales = request.POST.get('notas_generales', '')
        ficha_tecnica.save()
        
        # --- LÓGICA SEGÚN ESPECIALIDAD ---
        
        # Kinesiología: guardar lesión
        if especialidad == 'kinesiologia':
            zona = request.POST.get('nueva_lesion_zona', '').strip()
            fecha = request.POST.get('nueva_lesion_fecha', '').strip()
            if zona and fecha:
                Lesion.objects.create(
                    paciente=paciente,
                    fecha_lesion=fecha,
                    tipo_lesion=request.POST.get('nueva_lesion_tipo', 'otra'),
                    zona=zona,
                    descripcion=request.POST.get('nueva_lesion_descripcion', ''),
                    tratamiento=request.POST.get('nueva_lesion_tratamiento', ''),
                )
        
        # Nutrición
        elif especialidad == 'nutricion':
            peso = request.POST.get('peso_kg', '').strip()
            if peso:
                from historias_clinicas.models import ConsultaNutricional
                ConsultaNutricional.objects.create(
                    paciente=paciente,
                    profesional=profesional,
                    fecha=request.POST.get('fecha', date.today()),
                    peso_kg=peso,
                    altura_cm=request.POST.get('altura_cm') or None,
                    imc=request.POST.get('imc') or None,
                    perimetro_cintura_cm=request.POST.get('perimetro_cintura_cm') or None,
                    porcentaje_grasa=request.POST.get('porcentaje_grasa') or None,
                    porcentaje_musculo=request.POST.get('porcentaje_musculo') or None,
                    objetivo=request.POST.get('objetivo', ''),
                    plan_nutricional=request.POST.get('plan_nutricional', ''),
                    observaciones=request.POST.get('observaciones_nutricion', ''),
                )
        # Nota clínica (para todas las especialidades, especialmente útil en "general")
        titulo_nota = request.POST.get('nota_titulo', '').strip()
        contenido_nota = request.POST.get('nota_contenido', '').strip()
        if titulo_nota and contenido_nota:
            from historias_clinicas.models import NotaClinica
            NotaClinica.objects.create(
                paciente=paciente,
                profesional=profesional,
                fecha=request.POST.get('nota_fecha', date.today()),
                tipo=request.POST.get('nota_tipo', 'observacion'),
                titulo=titulo_nota,
                contenido=contenido_nota,
            )
        # Fonoaudiología
        elif especialidad == 'fonoaudiologia':
            area = request.POST.get('area', '').strip()
            if area:
                from historias_clinicas.models import EvaluacionFonoaudiologica
                EvaluacionFonoaudiologica.objects.create(
                    paciente=paciente,
                    profesional=profesional,
                    fecha=request.POST.get('fecha', date.today()),
                    area=area,
                    diagnostico=request.POST.get('diagnostico', ''),
                    evaluacion=request.POST.get('evaluacion', ''),
                    objetivos=request.POST.get('objetivos', ''),
                    ejercicios=request.POST.get('ejercicios', ''),
                    respuesta_paciente=request.POST.get('respuesta_paciente', ''),
                    recomendaciones=request.POST.get('recomendaciones', ''),
                )

        # Odontología: guardar tratamiento
        elif especialidad == 'odontologia':
            pieza = request.POST.get('nuevo_tratamiento_pieza', '').strip()
            tipo = request.POST.get('nuevo_tratamiento_tipo', '').strip()
            fecha = request.POST.get('nuevo_tratamiento_fecha', '').strip()
            if pieza and tipo:
                from historias_clinicas.models import TratamientoOdontologico
                TratamientoOdontologico.objects.create(
                    paciente=paciente,
                    profesional=profesional,
                    fecha=fecha or date.today(),
                    pieza_dental=pieza,
                    tipo_tratamiento=tipo,
                    material_usado=request.POST.get('nuevo_tratamiento_material', ''),
                    descripcion=request.POST.get('nuevo_tratamiento_descripcion', ''),
                    costo=request.POST.get('nuevo_tratamiento_costo') or None,
                    fecha_proximo_control=request.POST.get('nuevo_tratamiento_control') or None,
                )
        
        messages.success(request, '✅ Ficha guardada correctamente.')
        return redirect('ficha_tecnica', paciente_id=paciente.id)
    
    context = {
        'paciente': paciente,
        'ficha_tecnica': ficha_tecnica,
        'profesional': profesional,
        'hoy': date.today(),
        'notas': paciente.notas_clinicas.all(),
        'consultas': paciente.consultas_nutricionales.all() if especialidad == 'nutricion' else None,
        'evaluaciones': paciente.evaluaciones_fonoaudiologicas.all() if especialidad == 'fonoaudiologia' else None,
    }
    
    return render(request, template, context)


@login_required
def estudios_paciente(request, paciente_id):
    """Ver y subir estudios de un paciente (vista profesional)."""
    if request.user.rol not in ['profesional', 'secretaria']:
        messages.error(request, 'No tenés acceso.')
        return redirect('home')
    
    paciente = get_object_or_404(Paciente, id=paciente_id)
    
    if request.user.rol == 'secretaria':
        profesional = None
    elif request.user.rol == 'profesional':
        profesional = get_object_or_404(Profesional, usuario=request.user)
    else:
        profesional = None
    
    if request.method == 'POST':
        titulo = request.POST.get('titulo')
        descripcion = request.POST.get('descripcion', '')
        tipo_estudio = request.POST.get('tipo_estudio', 'otro')
        fecha_estudio = request.POST.get('fecha_estudio') or None
        archivo = request.FILES.get('archivo')
        
        if not titulo or not archivo:
            messages.error(request, 'El título y el archivo son obligatorios.')
            return redirect('estudios_paciente', paciente_id=paciente.id)
        
        EstudioMedico.objects.create(
            paciente=paciente,
            profesional=profesional,
            titulo=titulo,
            descripcion=descripcion,
            tipo_estudio=tipo_estudio,
            fecha_estudio=fecha_estudio,
            archivo=archivo
        )
        
        messages.success(request, f'Estudio "{titulo}" subido correctamente.')
        return redirect('estudios_paciente', paciente_id=paciente.id)
    
    estudios = paciente.estudios_medicos.all()
    
    return render(request, 'pacientes/estudios.html', {
        'paciente': paciente,
        'estudios': estudios,
        'tipos_estudio': EstudioMedico._meta.get_field('tipo_estudio').choices,
        'profesional': profesional,
        'es_secretaria': request.user.rol == 'secretaria'
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
    obras_sociales_disponibles = ObraSocial.objects.filter(activo=True)
    
    if request.user.rol == 'profesional':
        profesional = get_object_or_404(Profesional, usuario=request.user)
    else:
        profesional = None
    
    if request.method == 'POST':
        accion = request.POST.get('accion', '')
        
        # Guardar sesiones
        if accion == 'guardar_sesiones':
            sesiones_autorizadas = request.POST.get('sesiones_autorizadas')
            sesiones_restantes = request.POST.get('sesiones_restantes')
            fecha_vencimiento = request.POST.get('fecha_vencimiento')
            
            paciente.sesiones_autorizadas = int(sesiones_autorizadas) if sesiones_autorizadas else None
            paciente.sesiones_restantes = int(sesiones_restantes) if sesiones_restantes else None
            paciente.fecha_vencimiento_sesiones = fecha_vencimiento if fecha_vencimiento else None
            paciente.save()
            messages.success(request, '✅ Sesiones actualizadas correctamente.')
        
        # Agregar nueva obra social
        elif accion == 'agregar_obra_social':
            obra_social_id = request.POST.get('obra_social')
            plan_id = request.POST.get('plan')
            numero_afiliado = request.POST.get('numero_afiliado', '')
            
            if obra_social_id:
                # Desactivar otras obras sociales si se marca como principal
                if request.POST.get('es_principal') == 'si':
                    PacienteObraSocial.objects.filter(paciente=paciente, activa=True).update(activa=False)
                
                PacienteObraSocial.objects.create(
                    paciente=paciente,
                    obra_social_id=obra_social_id,
                    plan_id=plan_id if plan_id else None,
                    numero_afiliado=numero_afiliado,
                    activa=True
                )
                
                # Actualizar también el campo legacy de obra_social principal
                obra_social = ObraSocial.objects.get(id=obra_social_id)
                paciente.obra_social = obra_social
                paciente.numero_afiliado = numero_afiliado
                if plan_id:
                    paciente.plan_obra_social_id = plan_id
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
        
        # Establecer como principal
        elif accion == 'establecer_principal':
            os_id = request.POST.get('os_id')
            # Desactivar todas
            PacienteObraSocial.objects.filter(paciente=paciente).update(activa=False)
            # Activar la seleccionada
            obra_social_paciente = get_object_or_404(PacienteObraSocial, id=os_id, paciente=paciente)
            obra_social_paciente.activa = True
            obra_social_paciente.save()
            
            # Actualizar campo legacy
            paciente.obra_social = obra_social_paciente.obra_social
            paciente.numero_afiliado = obra_social_paciente.numero_afiliado
            paciente.plan_obra_social = obra_social_paciente.plan
            paciente.save()
            
            messages.success(request, '⭐ Obra social principal actualizada.')
        
        return redirect('gestionar_obras_sociales', paciente_id=paciente.id)
    
    context = {
        'paciente': paciente,
        'profesional': profesional,
        'obras_sociales_disponibles': obras_sociales_disponibles,
        'hoy': date.today(),
        'es_secretaria': request.user.rol == 'secretaria',
    }
    
    return render(request, 'pacientes/gestionar_obras_sociales.html', context)