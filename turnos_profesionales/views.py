from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from datetime import date, timedelta, datetime

from .models import TurnoProfesional
from profesionales.models import Profesional
from pacientes.models import Paciente
from agendas.models import Agenda, HorarioAtencion, BloqueoAgenda
from historias_clinicas.models import HistoriaClinica, Evolucion


# ============ PANEL PROFESIONAL ============

@login_required
def panel_profesional(request):
    """Panel principal del profesional. Muestra turnos del día."""
    if request.user.rol not in ['profesional', 'secretaria']:
        messages.error(request, 'No tenés acceso a esta sección.')
        return redirect('home')
    
    # Si es secretaria, puede ver el panel de cualquier profesional
    if request.user.rol == 'secretaria':
        profesional_id = request.GET.get('profesional')
        if profesional_id:
            profesional = get_object_or_404(Profesional, id=profesional_id)
        else:
            profesional = Profesional.objects.filter(
                establecimiento=request.user.establecimiento, activo=True
            ).first()
            if not profesional:
                messages.error(request, 'No hay profesionales en el consultorio.')
                return redirect('panel_secretaria')
    else:
        profesional = get_object_or_404(Profesional, usuario=request.user)
    
    hoy = date.today()
    
    # Turnos de hoy
    turnos_hoy = TurnoProfesional.objects.filter(
        profesional=profesional,
        fecha=hoy
    ).order_by('hora_inicio')
    
    # Turnos de mañana
    manana = hoy + timedelta(days=1)
    turnos_manana = TurnoProfesional.objects.filter(
        profesional=profesional,
        fecha=manana
    ).order_by('hora_inicio')
    
    # Próximos turnos (7 días)
    proxima_semana = hoy + timedelta(days=7)
    proximos_turnos = TurnoProfesional.objects.filter(
        profesional=profesional,
        fecha__range=[manana + timedelta(days=1), proxima_semana],
        estado__in=['pendiente', 'confirmado']
    ).order_by('fecha', 'hora_inicio')
    
    contexto = {
        'profesional': profesional,
        'hoy': hoy,
        'turnos_hoy': turnos_hoy,
        'turnos_manana': turnos_manana,
        'proximos_turnos': proximos_turnos,
        'total_hoy': turnos_hoy.count(),
        'confirmados_hoy': turnos_hoy.filter(estado='confirmado').count(),
        'pendientes_hoy': turnos_hoy.filter(estado='pendiente').count(),
        'completados_hoy': turnos_hoy.filter(estado='completado').count(),
    }
    
    return render(request, 'turnos_profesionales/panel.html', contexto)


# ============ ACCIONES SOBRE TURNOS ============

@login_required
def confirmar_turno(request, turno_id):
    turno = get_object_or_404(TurnoProfesional, id=turno_id)
    if request.user.rol not in ['profesional', 'secretaria']:
        messages.error(request, 'No tenés permiso.')
        return redirect('panel_profesional')
    
    turno.estado = 'confirmado'
    turno.save()
    messages.success(request, f'Turno de {turno.paciente.nombre_completo} confirmado.')
    
    if request.user.rol == 'secretaria':
        return redirect('panel_secretaria')
    return redirect('panel_profesional')


@login_required
def cancelar_turno(request, turno_id):
    turno = get_object_or_404(TurnoProfesional, id=turno_id)
    if request.user.rol not in ['profesional', 'secretaria']:
        messages.error(request, 'No tenés permiso.')
        return redirect('panel_profesional')
    
    turno.estado = 'cancelado'
    turno.save()
    messages.warning(request, f'Turno de {turno.paciente.nombre_completo} cancelado.')
    
    if request.user.rol == 'secretaria':
        return redirect('panel_secretaria')
    return redirect('panel_profesional')


@login_required
def completar_turno(request, turno_id):
    turno = get_object_or_404(TurnoProfesional, id=turno_id)
    if request.user.rol not in ['profesional', 'secretaria']:
        messages.error(request, 'No tenés permiso.')
        return redirect('panel_profesional')
    
    turno.estado = 'completado'
    turno.save()
    
    # Descontar sesión si el paciente tiene sesiones
    paciente = turno.paciente
    if paciente.sesiones_restantes is not None and paciente.sesiones_restantes > 0:
        paciente.sesiones_restantes -= 1
        paciente.save()
        
        # Alerta si quedan pocas sesiones
        if paciente.sesiones_restantes <= 3:
            messages.warning(
                request, 
                f'⚠️ ¡Atención! A {paciente.nombre_completo} le quedan solo {paciente.sesiones_restantes} sesiones.'
            )
        else:
            messages.success(
                request,
                f'Turno completado. Sesiones restantes de {paciente.nombre_completo}: {paciente.sesiones_restantes}'
            )
    else:
        messages.success(request, f'Turno de {paciente.nombre_completo} completado.')
    
    # Solo el profesional puede cargar evolución
    if request.user.rol == 'secretaria':
        if request.user.rol == 'secretaria':
            return redirect('panel_secretaria')
    return redirect('cargar_evolucion', turno_id=turno.id)


@login_required
def no_asistio_turno(request, turno_id):
    turno = get_object_or_404(TurnoProfesional, id=turno_id)
    if request.user.rol not in ['profesional', 'secretaria']:
        messages.error(request, 'No tenés permiso.')
        return redirect('panel_profesional')
    
    turno.estado = 'no_asistio'
    turno.save()
    messages.warning(request, f'{turno.paciente.nombre_completo} no asistió.')
    
    if request.user.rol == 'secretaria':
        return redirect('panel_secretaria')
    return redirect('panel_profesional')

# ============ CARGA DE EVOLUCIÓN (SOLO PROFESIONAL) ============

@login_required
def cargar_evolucion(request, turno_id):
    """Carga la evolución después de completar un turno. Solo profesional."""
    if request.user.rol != 'profesional':
        messages.error(request, 'Solo el profesional puede cargar evoluciones.')
        return redirect('home')
    
    turno = get_object_or_404(TurnoProfesional, id=turno_id)
    profesional = get_object_or_404(Profesional, usuario=request.user)
    
    if request.user != turno.profesional.usuario:
        messages.error(request, 'No tenés permiso.')
        return redirect('panel_profesional')
    
    historia = HistoriaClinica.objects.filter(paciente=turno.paciente).first()
    
    if not historia:
        historia = HistoriaClinica.objects.create(
            paciente=turno.paciente,
            numero_historia=f"HC-{turno.paciente.id:06d}"
        )
    
    if request.method == 'POST':
        motivo = request.POST.get('motivo')
        diagnostico = request.POST.get('diagnostico', '')
        tratamiento = request.POST.get('tratamiento', '')
        indicaciones = request.POST.get('indicaciones', '')
        proximo_control = request.POST.get('proximo_control', '')
        
        if not motivo:
            messages.error(request, 'El motivo de consulta es obligatorio.')
            return redirect('cargar_evolucion', turno_id=turno.id)
        
        evolucion = Evolucion.objects.create(
            historia_clinica=historia,
            turno=turno,
            profesional=profesional,
            motivo_consulta=motivo,
            diagnostico=diagnostico,
            tratamiento_realizado=tratamiento,
            indicaciones=indicaciones,
            proximo_control=proximo_control if proximo_control else None
        )
        
        messages.success(request, 'Evolución cargada correctamente.')
        return redirect('panel_profesional')
    
    return render(request, 'turnos_profesionales/cargar_evolucion.html', {
        'profesional': profesional,
        'turno': turno,
        'historia': historia
    })


# ============ ASIGNAR TURNO A PACIENTE ============

@login_required
def asignar_turno(request, paciente_id):
    """Asigna un turno a un paciente existente."""
    if request.user.rol not in ['profesional', 'secretaria']:
        return redirect('home')
    
    # Obtener profesional según el rol
    if request.user.rol == 'secretaria':
        profesional_id = request.GET.get('profesional')
        if profesional_id:
            profesional = get_object_or_404(Profesional, id=profesional_id)
        else:
            profesional = Profesional.objects.filter(
                establecimiento=request.user.establecimiento, activo=True
            ).first()
    else:
        profesional = get_object_or_404(Profesional, usuario=request.user)
    
    paciente = get_object_or_404(Paciente, id=paciente_id)
    hoy = date.today()
    
    if request.method == 'POST':
        fecha_str = request.POST.get('fecha')
        hora_str = request.POST.get('hora')
        tipo_consulta = request.POST.get('tipo_consulta', '')
        notas = request.POST.get('notas', '')
        
        if not all([fecha_str, hora_str]):
            messages.error(request, 'Seleccioná fecha y hora.')
            return redirect('asignar_turno', paciente_id=paciente.id)
        
        try:
            fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
            hora = datetime.strptime(hora_str, '%H:%M').time()
        except ValueError:
            messages.error(request, 'Fecha u hora inválida.')
            return redirect('asignar_turno', paciente_id=paciente.id)
        
        # Verificar disponibilidad
        agenda = Agenda.objects.filter(
            profesional=profesional,
            activo=True,
            fecha_inicio__lte=fecha,
        ).filter(
            Q(fecha_fin__isnull=True) | Q(fecha_fin__gte=fecha)
        ).first()
        
        if not agenda:
            messages.error(request, 'No hay agenda configurada para esa fecha.')
            return redirect('asignar_turno', paciente_id=paciente.id)
        
        dia_semana = fecha.weekday()
        horario = HorarioAtencion.objects.filter(
            agenda=agenda,
            dia=dia_semana
        ).first()
        
        if not horario:
            messages.error(request, 'El profesional no atiende ese día.')
            return redirect('asignar_turno', paciente_id=paciente.id)
        
        # Verificar si ya hay turno
        existe = TurnoProfesional.objects.filter(
            profesional=profesional,
            fecha=fecha,
            hora_inicio=hora,
            estado__in=['pendiente', 'confirmado']
        ).exists()
        
        if existe:
            messages.error(request, 'Ese horario ya está ocupado.')
            return redirect('asignar_turno', paciente_id=paciente.id)
        
        hora_fin = (datetime.combine(fecha, hora) + timedelta(minutes=horario.duracion_turno)).time()
        
        TurnoProfesional.objects.create(
            profesional=profesional,
            paciente=paciente,
            fecha=fecha,
            hora_inicio=hora,
            hora_fin=hora_fin,
            estado='pendiente',
            tipo_consulta=tipo_consulta,
            notas_internas=notas
        )
        
        messages.success(request, f'Turno asignado a {paciente.nombre_completo} el {fecha.strftime("%d/%m/%Y")} a las {hora_str}.')
        
        if request.user.rol == 'secretaria':
            return redirect('panel_secretaria')
        return redirect('panel_profesional')
    
    # GET - Mostrar horarios disponibles
    dias_disponibles = []
    agenda = Agenda.objects.filter(
        profesional=profesional,
        activo=True,
        fecha_inicio__lte=hoy + timedelta(days=30)
    ).first()
    
    if agenda:
        for i in range(30):
            fecha = hoy + timedelta(days=i)
            dia_semana = fecha.weekday()
            
            horario = HorarioAtencion.objects.filter(
                agenda=agenda,
                dia=dia_semana
            ).first()
            
            if horario:
                hora_actual = horario.hora_inicio
                slots = []
                
                while hora_actual < horario.hora_fin:
                    hora_fin_slot = (datetime.combine(fecha, hora_actual) + timedelta(minutes=horario.duracion_turno)).time()
                    
                    if hora_fin_slot <= horario.hora_fin:
                        ocupado = TurnoProfesional.objects.filter(
                            profesional=profesional,
                            fecha=fecha,
                            hora_inicio=hora_actual,
                            estado__in=['pendiente', 'confirmado']
                        ).exists()
                        
                        if not ocupado:
                            slots.append(hora_actual.strftime('%H:%M'))
                    
                    hora_actual = hora_fin_slot
                
                if slots:
                    dias_disponibles.append({
                        'fecha': fecha,
                        'fecha_str': fecha.strftime('%Y-%m-%d'),
                        'nombre_dia': fecha.strftime('%A'),
                        'slots': slots
                    })
    
    # Si es secretaria, pasar lista de profesionales
    profesionales_consultorio = None
    if request.user.rol == 'secretaria':
        profesionales_consultorio = Profesional.objects.filter(
            establecimiento=request.user.establecimiento, activo=True
        )
    
    return render(request, 'turnos_profesionales/asignar_turno.html', {
        'profesional': profesional,
        'paciente': paciente,
        'dias_disponibles': dias_disponibles,
        'hoy': hoy,
        'profesionales_consultorio': profesionales_consultorio,
    })


# ============ EDITAR TURNO ============

@login_required
def editar_turno(request, turno_id):
    """Editar un turno existente (cambiar fecha, hora, estado, notas)."""
    if request.user.rol not in ['profesional', 'secretaria']:
        return redirect('home')
    
    turno = get_object_or_404(TurnoProfesional, id=turno_id)
    
    if request.user.rol == 'secretaria':
        profesional = turno.profesional  # La secretaria edita el turno del profesional que lo tiene
    else:
        profesional = get_object_or_404(Profesional, usuario=request.user)
        if request.user != turno.profesional.usuario:
            messages.error(request, 'No tenés permiso para editar este turno.')
            return redirect('panel_profesional')
    
    hoy = date.today()
    
    if request.method == 'POST':
        fecha_str = request.POST.get('fecha')
        hora_str = request.POST.get('hora')
        estado = request.POST.get('estado')
        tipo_consulta = request.POST.get('tipo_consulta', '')
        notas = request.POST.get('notas', '')
        
        if not all([fecha_str, hora_str, estado]):
            messages.error(request, 'Completá fecha, hora y estado.')
            return redirect('editar_turno_pro', turno_id=turno.id)
        
        try:
            fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
            hora = datetime.strptime(hora_str, '%H:%M').time()
        except ValueError:
            messages.error(request, 'Fecha u hora inválida.')
            return redirect('editar_turno_pro', turno_id=turno.id)
        
        # Si cambió la fecha/hora, verificar disponibilidad
        if fecha != turno.fecha or hora != turno.hora_inicio:
            existe = TurnoProfesional.objects.filter(
                profesional=profesional,
                fecha=fecha,
                hora_inicio=hora,
                estado__in=['pendiente', 'confirmado']
            ).exclude(id=turno.id).exists()
            
            if existe:
                messages.error(request, 'Ese horario ya está ocupado.')
                return redirect('editar_turno_pro', turno_id=turno.id)
        
        turno.fecha = fecha
        turno.hora_inicio = hora
        turno.estado = estado
        turno.tipo_consulta = tipo_consulta
        turno.notas_internas = notas

        # Recalcular hora_fin según la duración configurada en la agenda
        agenda = Agenda.objects.filter(
            profesional=profesional,
            activo=True,
            fecha_inicio__lte=fecha
        ).filter(
            Q(fecha_fin__isnull=True) | Q(fecha_fin__gte=fecha)
        ).first()
        
        duracion = 30  # default
        if agenda:
            dia_semana = fecha.weekday()
            horario_atencion = HorarioAtencion.objects.filter(
                agenda=agenda,
                dia=dia_semana
            ).first()
            if horario_atencion:
                duracion = horario_atencion.duracion_turno
        
        turno.hora_fin = (datetime.combine(fecha, hora) + timedelta(minutes=duracion)).time()
        turno.save()
        
        messages.success(request, 'Turno actualizado correctamente.')
        
        if request.user.rol == 'secretaria':
            return redirect('panel_secretaria')
        return redirect('panel_profesional')
    
    # GET - Mostrar formulario con horarios disponibles
    dias_disponibles = []
    agenda = Agenda.objects.filter(
        profesional=profesional,
        activo=True,
        fecha_inicio__lte=hoy + timedelta(days=30)
    ).first()
    
    if agenda:
        for i in range(30):
            fecha = hoy + timedelta(days=i)
            dia_semana = fecha.weekday()
            
            horario = HorarioAtencion.objects.filter(
                agenda=agenda,
                dia=dia_semana
            ).first()
            
            if horario:
                hora_actual = horario.hora_inicio
                slots = []
                
                while hora_actual < horario.hora_fin:
                    hora_fin_slot = (datetime.combine(fecha, hora_actual) + timedelta(minutes=horario.duracion_turno)).time()
                    
                    if hora_fin_slot <= horario.hora_fin:
                        ocupado = TurnoProfesional.objects.filter(
                            profesional=profesional,
                            fecha=fecha,
                            hora_inicio=hora_actual,
                            estado__in=['pendiente', 'confirmado']
                        ).exclude(id=turno.id).exists()
                        
                        if not ocupado or (fecha == turno.fecha and hora_actual == turno.hora_inicio):
                            slots.append(hora_actual.strftime('%H:%M'))
                    
                    hora_actual = hora_fin_slot
                
                if slots:
                    dias_disponibles.append({
                        'fecha': fecha,
                        'fecha_str': fecha.strftime('%Y-%m-%d'),
                        'nombre_dia': fecha.strftime('%A'),
                        'slots': slots
                    })
    
    return render(request, 'turnos_profesionales/editar_turno.html', {
        'profesional': profesional,
        'turno': turno,
        'dias_disponibles': dias_disponibles,
        'hoy': hoy
    })


# ============ CALENDARIO SEMANAL ============

@login_required
def calendario_semanal(request):
    """Vista de calendario semanal para profesional o secretaria."""
    if request.user.rol not in ['profesional', 'secretaria']:
        return redirect('home')
    
    # Si es secretaria, puede ver calendario de cualquier profesional
    if request.user.rol == 'secretaria':
        profesional_id = request.GET.get('profesional')
        if profesional_id:
            profesional = get_object_or_404(Profesional, id=profesional_id)
        else:
            profesional = Profesional.objects.filter(
                establecimiento=request.user.establecimiento, activo=True
            ).first()
            if not profesional:
                messages.error(request, 'No hay profesionales en el consultorio.')
                return redirect('panel_secretaria')
    else:
        profesional = get_object_or_404(Profesional, usuario=request.user)
    
    # Determinar la semana a mostrar (por defecto la actual)
    fecha_str = request.GET.get('fecha')
    if fecha_str:
        try:
            fecha_base = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        except ValueError:
            fecha_base = date.today()
    else:
        fecha_base = date.today()
    
    hoy = date.today()
    
    # Encontrar el lunes de esa semana
    lunes = fecha_base - timedelta(days=fecha_base.weekday())
    
    # Crear los 7 días de la semana
    dias_semana = []
    nombres_dias = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
    
    for i in range(7):
        dia = lunes + timedelta(days=i)
        
        # Obtener turnos de ese día
        turnos_dia = TurnoProfesional.objects.filter(
            profesional=profesional,
            fecha=dia
        ).order_by('hora_inicio')
        
        # Determinar si el profesional atiende ese día
        agenda = Agenda.objects.filter(
            profesional=profesional,
            activo=True,
            fecha_inicio__lte=dia
        ).filter(
            Q(fecha_fin__isnull=True) | Q(fecha_fin__gte=dia)
        ).first()
        
        # Verificar si el día está bloqueado
        bloqueos_dia = []
        if agenda:
            bloqueos_dia = BloqueoAgenda.objects.filter(
                agenda=agenda,
                fecha=dia,
                activo=True
            )
        
        horarios_dia = []
        if agenda:
            horarios = HorarioAtencion.objects.filter(
                agenda=agenda,
                dia=dia.weekday()
            )
            for h in horarios:
                hora_actual = h.hora_inicio
                while hora_actual < h.hora_fin:
                    hora_fin_slot = (datetime.combine(dia, hora_actual) + 
                                    timedelta(minutes=h.duracion_turno)).time()
                    
                    if hora_fin_slot <= h.hora_fin:
                        turno_en_slot = None
                        for t in turnos_dia:
                            if t.hora_inicio == hora_actual:
                                turno_en_slot = t
                                break
                        
                        # Verificar si el slot está bloqueado
                        slot_bloqueado = False
                        for b in bloqueos_dia:
                            if b.hora_inicio is None and b.hora_fin is None:
                                slot_bloqueado = True
                            elif b.hora_inicio and b.hora_fin:
                                if hora_actual >= b.hora_inicio and hora_fin_slot <= b.hora_fin:
                                    slot_bloqueado = True
                        
                        if not slot_bloqueado:
                            horarios_dia.append({
                                'hora_inicio': hora_actual,
                                'hora_fin': hora_fin_slot,
                                'turno': turno_en_slot,
                                'disponible': turno_en_slot is None
                            })
                    
                    hora_actual = hora_fin_slot
        
        # Determinar si está bloqueado el día completo
        dia_completo_bloqueado = False
        for b in bloqueos_dia:
            if b.hora_inicio is None and b.hora_fin is None:
                dia_completo_bloqueado = True
                break
        
        dias_semana.append({
            'fecha': dia,
            'nombre': nombres_dias[i],
            'es_hoy': dia == hoy,
            'atiende': len(horarios_dia) > 0,
            'bloqueado': dia_completo_bloqueado,
            'bloqueos': bloqueos_dia,
            'horarios': horarios_dia,
            'total_turnos': turnos_dia.count()
        })
    
    # Semanas anterior y siguiente
    semana_anterior = lunes - timedelta(days=7)
    semana_siguiente = lunes + timedelta(days=7)
    
    # Si es secretaria, pasar lista de profesionales
    profesionales_consultorio = None
    if request.user.rol == 'secretaria':
        profesionales_consultorio = Profesional.objects.filter(
            establecimiento=request.user.establecimiento, activo=True
        )
    
    return render(request, 'turnos_profesionales/calendario.html', {
        'profesional': profesional,
        'dias_semana': dias_semana,
        'lunes': lunes,
        'domingo': lunes + timedelta(days=6),
        'semana_anterior': semana_anterior.strftime('%Y-%m-%d'),
        'semana_siguiente': semana_siguiente.strftime('%Y-%m-%d'),
        'hoy': hoy,
        'profesionales_consultorio': profesionales_consultorio,
    })


# ============ ASIGNAR TURNO DESDE CALENDARIO ============

@login_required
def asignar_turno_calendario(request):
    """Asignar turno desde el calendario con fecha y hora predefinidas."""
    if request.user.rol not in ['profesional', 'secretaria']:
        return redirect('home')
    
    # Obtener profesional según el rol
    if request.user.rol == 'secretaria':
        profesional_id = request.GET.get('profesional')
        if profesional_id:
            profesional = get_object_or_404(Profesional, id=profesional_id)
        else:
            profesional = Profesional.objects.filter(
                establecimiento=request.user.establecimiento, activo=True
            ).first()
    else:
        profesional = get_object_or_404(Profesional, usuario=request.user)
    
    fecha_str = request.GET.get('fecha', '')
    hora_str = request.GET.get('hora', '')
    
    if not fecha_str or not hora_str:
        messages.error(request, 'Falta fecha u hora.')
        return redirect('calendario_semanal')
    
    try:
        fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        hora = datetime.strptime(hora_str, '%H:%M').time()
    except ValueError:
        messages.error(request, 'Fecha u hora inválida.')
        return redirect('calendario_semanal')
    
    # Calcular hora_fin
    duracion = 30
    agenda = Agenda.objects.filter(
        profesional=profesional,
        activo=True,
        fecha_inicio__lte=fecha
    ).filter(
        Q(fecha_fin__isnull=True) | Q(fecha_fin__gte=fecha)
    ).first()
    
    if agenda:
        dia_semana = fecha.weekday()
        horario_atencion = HorarioAtencion.objects.filter(
            agenda=agenda,
            dia=dia_semana
        ).first()
        if horario_atencion:
            duracion = horario_atencion.duracion_turno
    
    hora_fin = (datetime.combine(fecha, hora) + timedelta(minutes=duracion)).time()
    
    if request.method == 'POST':
        paciente_id = request.POST.get('paciente_id')
        tipo_consulta = request.POST.get('tipo_consulta', '')
        notas = request.POST.get('notas', '')
        
        if not paciente_id:
            messages.error(request, 'Seleccioná un paciente.')
            return redirect(f'{request.path}?fecha={fecha_str}&hora={hora_str}')
        
        paciente = get_object_or_404(Paciente, id=paciente_id)
        
        # Verificar que no esté ocupado
        existe = TurnoProfesional.objects.filter(
            profesional=profesional,
            fecha=fecha,
            hora_inicio=hora,
            estado__in=['pendiente', 'confirmado']
        ).exists()
        
        if existe:
            messages.error(request, 'Ese horario ya fue ocupado.')
            return redirect('calendario_semanal')
        
        TurnoProfesional.objects.create(
            profesional=profesional,
            paciente=paciente,
            fecha=fecha,
            hora_inicio=hora,
            hora_fin=hora_fin,
            estado='pendiente',
            tipo_consulta=tipo_consulta,
            notas_internas=notas
        )
        
        messages.success(request, f'Turno asignado a {paciente.nombre_completo} el {fecha.strftime("%d/%m/%Y")} a las {hora_str}.')
        return redirect('calendario_semanal')
    
    # GET - Mostrar formulario con búsqueda de pacientes
    busqueda = request.GET.get('buscar', '')
    pacientes = []
    if busqueda:
        pacientes = Paciente.objects.filter(
            Q(nombre__icontains=busqueda) |
            Q(apellido__icontains=busqueda) |
            Q(dni__icontains=busqueda)
        )[:15]
    
    return render(request, 'turnos_profesionales/asignar_calendario.html', {
        'profesional': profesional,
        'fecha': fecha,
        'hora': hora,
        'hora_fin': hora_fin,
        'fecha_str': fecha_str,
        'hora_str': hora_str,
        'pacientes': pacientes,
        'busqueda': busqueda
    })


# ============ BLOQUEAR/DESBLOQUEAR DÍAS ============

@login_required
def bloquear_dia(request):
    """Bloquear un día o rango horario."""
    if request.user.rol not in ['profesional', 'secretaria']:
        return redirect('home')
    
    if request.user.rol == 'secretaria':
        profesional_id = request.GET.get('profesional')
        if profesional_id:
            profesional = get_object_or_404(Profesional, id=profesional_id)
        else:
            profesional = Profesional.objects.filter(
                establecimiento=request.user.establecimiento, activo=True
            ).first()
    else:
        profesional = get_object_or_404(Profesional, usuario=request.user)
    
    if request.method == 'POST':
        fecha = request.POST.get('fecha')
        hora_inicio = request.POST.get('hora_inicio', '')
        hora_fin = request.POST.get('hora_fin', '')
        motivo = request.POST.get('motivo', '')
        dia_completo = request.POST.get('dia_completo') == 'on'
        
        if not fecha:
            messages.error(request, 'Seleccioná una fecha.')
            return redirect('calendario_semanal')
        
        try:
            fecha_date = datetime.strptime(fecha, '%Y-%m-%d').date()
        except ValueError:
            messages.error(request, 'Fecha inválida.')
            return redirect('calendario_semanal')
        
        # Obtener o crear agenda
        agenda = Agenda.objects.filter(
            profesional=profesional,
            activo=True,
            fecha_inicio__lte=fecha_date
        ).filter(
            Q(fecha_fin__isnull=True) | Q(fecha_fin__gte=fecha_date)
        ).first()
        
        if not agenda:
            messages.error(request, 'No tenés agenda configurada para esa fecha.')
            return redirect('calendario_semanal')
        
        # Crear bloqueo
        BloqueoAgenda.objects.create(
            agenda=agenda,
            fecha=fecha_date,
            hora_inicio=datetime.strptime(hora_inicio, '%H:%M').time() if hora_inicio and not dia_completo else None,
            hora_fin=datetime.strptime(hora_fin, '%H:%M').time() if hora_fin and not dia_completo else None,
            motivo=motivo if motivo else 'Día no laborable'
        )
        
        messages.success(request, f'Día {fecha_date.strftime("%d/%m/%Y")} bloqueado.')
        return redirect('calendario_semanal')
    
    return redirect('calendario_semanal')


@login_required
def desbloquear_dia(request, bloqueo_id):
    """Desbloquear un día."""
    if request.user.rol not in ['profesional', 'secretaria']:
        return redirect('home')
    
    bloqueo = get_object_or_404(BloqueoAgenda, id=bloqueo_id)
    
    if request.user.rol == 'secretaria':
        if bloqueo.agenda.profesional.establecimiento != request.user.establecimiento:
            messages.error(request, 'No tenés permiso.')
            return redirect('calendario_semanal')
    else:
        profesional = get_object_or_404(Profesional, usuario=request.user)
        if bloqueo.agenda.profesional != profesional:
            messages.error(request, 'No tenés permiso.')
            return redirect('calendario_semanal')
    
    bloqueo.activo = False
    bloqueo.save()
    
    messages.success(request, f'Bloqueo del {bloqueo.fecha.strftime("%d/%m/%Y")} eliminado.')
    return redirect('calendario_semanal')


# ============ PANEL SECRETARIA ============

@login_required
def panel_secretaria(request):
    """Panel para la secretaria/recepcionista del consultorio."""
    if request.user.rol != 'secretaria':
        messages.error(request, 'No tenés acceso.')
        return redirect('home')
    
    if not request.user.establecimiento:
        messages.error(request, 'No tenés un consultorio asignado.')
        return redirect('home')
    
    establecimiento = request.user.establecimiento
    hoy = date.today()
    
    # Obtener todos los profesionales del consultorio
    profesionales = Profesional.objects.filter(
        establecimiento=establecimiento,
        activo=True
    )
    
    # Si se selecciona un profesional específico
    profesional_id = request.GET.get('profesional')
    profesional_seleccionado = None
    if profesional_id:
        profesional_seleccionado = get_object_or_404(Profesional, 
                                                      id=profesional_id, 
                                                      establecimiento=establecimiento)
    
    # Turnos de hoy (todos o de un profesional)
    if profesional_seleccionado:
        turnos_hoy = TurnoProfesional.objects.filter(
            profesional=profesional_seleccionado,
            fecha=hoy
        ).order_by('hora_inicio')
    else:
        turnos_hoy = TurnoProfesional.objects.filter(
            profesional__in=profesionales,
            fecha=hoy
        ).order_by('profesional', 'hora_inicio')
    
    # Estadísticas
    total_hoy = turnos_hoy.count()
    pendientes = turnos_hoy.filter(estado='pendiente').count()
    confirmados = turnos_hoy.filter(estado='confirmado').count()
    en_sala = turnos_hoy.filter(estado='en_sala').count()
    
    return render(request, 'turnos_profesionales/panel_secretaria.html', {
        'profesionales': profesionales,
        'profesional_seleccionado': profesional_seleccionado,
        'turnos_hoy': turnos_hoy,
        'hoy': hoy,
        'total_hoy': total_hoy,
        'pendientes': pendientes,
        'confirmados': confirmados,
        'en_sala': en_sala,
        'establecimiento': establecimiento,
    })