from datetime import date
from turnos_profesionales.models import TurnoProfesional
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from .models import Paciente
from usuarios.models import Usuario
import random, string
from profesionales.models import Profesional
from obras_sociales.models import ObraSocial, Plan
from historias_clinicas.models import FichaTecnica, HistoriaClinica, Evolucion



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
        obra_social_id = request.POST.get('obra_social', '')
        plan_obra_social_id = request.POST.get('plan_obra_social', '')
        numero_afiliado = request.POST.get('numero_afiliado', '')
        sesiones_autorizadas = request.POST.get('sesiones_autorizadas', '')
        sesiones_restantes = request.POST.get('sesiones_restantes', '')
        fecha_vencimiento = request.POST.get('fecha_vencimiento', '')
        
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
            sesiones_autorizadas=int(sesiones_autorizadas) if sesiones_autorizadas else None,
            sesiones_restantes=int(sesiones_restantes) if sesiones_restantes else None,
            fecha_vencimiento_sesiones=fecha_vencimiento if fecha_vencimiento else None,
        )
        
        if obra_social_id:
            paciente.obra_social = ObraSocial.objects.get(id=obra_social_id)
            paciente.save()
        
        if plan_obra_social_id:
            paciente.plan_obra_social = Plan.objects.get(id=plan_obra_social_id)

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
    
    obras_sociales = ObraSocial.objects.filter(activo=True)
    return render(request, 'pacientes/registrar.html', {
        'profesional': profesional,
        'obras_sociales': obras_sociales
    })


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
        
        obra_social_id = request.POST.get('obra_social', '')
        if obra_social_id:
            paciente.obra_social = ObraSocial.objects.get(id=obra_social_id)
        else:
            paciente.obra_social = None

        plan_obra_social_id = request.POST.get('plan_obra_social', '')
        if plan_obra_social_id:
            paciente.plan_obra_social = Plan.objects.get(id=plan_obra_social_id)
        else:
            paciente.plan_obra_social = None    
        
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
    """Ficha técnica específica según la especialidad del profesional."""
    if request.user.rol not in ['profesional', 'secretaria']:
        messages.error(request, 'No tenés acceso.')
        return redirect('home')
    
    paciente = get_object_or_404(Paciente, id=paciente_id)
    
    # Obtener el profesional
    if request.user.rol == 'profesional':
        profesional = get_object_or_404(Profesional, usuario=request.user)
    else:
        profesional = Profesional.objects.first()
    
    # Obtener o crear la ficha técnica
    ficha_tecnica, created = FichaTecnica.objects.get_or_create(
        paciente=paciente,
        defaults={
            'profesional': profesional,
            'especialidad': profesional.especialidad if profesional else 'general'
        }
    )
    
    # Templates por especialidad
    templates_por_especialidad = {
        'odontologia': 'pacientes/fichas_especialidades/odontologia.html',
        'kinesiologia': 'pacientes/fichas_especialidades/kinesiologia.html',
    }
    
    especialidad = profesional.especialidad if profesional else 'general'
    template = templates_por_especialidad.get(
        especialidad, 
        'pacientes/fichas_especialidades/default.html'
    )
    
    if request.method == 'POST':
        # Guardar todos los datos del POST en el JSON
        datos = {}
        for key, value in request.POST.items():
            if key not in ['csrfmiddlewaretoken', 'notas_generales']:
                datos[key] = value
        
        ficha_tecnica.datos_especificos = datos
        ficha_tecnica.notas_generales = request.POST.get('notas_generales', '')
        ficha_tecnica.save()
        
        messages.success(request, 'Ficha técnica guardada correctamente.')
        return redirect('ficha_tecnica', paciente_id=paciente.id)
    
    context = {
        'paciente': paciente,
        'ficha_tecnica': ficha_tecnica,
        'profesional': profesional,
    }
    
    return render(request, template, context)