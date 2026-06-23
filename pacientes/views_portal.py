from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from datetime import date, timedelta, datetime

from establecimientos.models import Establecimiento
from core_app.models import ClienteSaaS, ConfiguracionSistema

from .models import Paciente
from profesionales.models import Profesional
from turnos_profesionales.models import TurnoProfesional
from agendas.models import Agenda, HorarioAtencion


@login_required
def panel_paciente(request):
    """Panel principal del paciente."""
    if request.user.rol != 'paciente':
        messages.error(request, 'No tenés acceso.')
        return redirect('home')
    
    try:
        paciente = Paciente.objects.get(usuario=request.user)
    except Paciente.DoesNotExist:
        messages.error(request, 'No tenés un perfil de paciente asociado.')
        return redirect('home')
    
    hoy = date.today()
    
    # Obtener cliente SaaS de la sesión para filtrar profesionales
    cliente_slug = request.session.get('cliente_slug')
    cliente = None
    if cliente_slug:
        try:
            cliente = ClienteSaaS.objects.get(slug=cliente_slug, activo=True)
        except ClienteSaaS.DoesNotExist:
            pass
    
    # Próximos turnos
    proximos_turnos = TurnoProfesional.objects.filter(
        paciente=paciente,
        fecha__gte=hoy,
        estado__in=['pendiente', 'confirmado']
    ).order_by('fecha', 'hora_inicio')[:10]
    
    # Últimos turnos
    ultimos_turnos = TurnoProfesional.objects.filter(
        paciente=paciente,
        estado='completado'
    ).order_by('-fecha', '-hora_inicio')[:5]
    
    return render(request, 'pacientes/portal/panel.html', {
        'paciente': paciente,
        'proximos_turnos': proximos_turnos,
        'ultimos_turnos': ultimos_turnos,
        'cliente': cliente,  # pasar al template
    })


@login_required
def mis_turnos(request):
    """Lista de todos los turnos del paciente."""
    if request.user.rol != 'paciente':
        return redirect('home')
    
    paciente = get_object_or_404(Paciente, usuario=request.user)
    
    turnos = TurnoProfesional.objects.filter(
        paciente=paciente
    ).order_by('-fecha', '-hora_inicio')[:30]
    
    return render(request, 'pacientes/portal/mis_turnos.html', {
        'paciente': paciente,
        'turnos': turnos
    })


@login_required
def cancelar_turno_paciente(request, turno_id):
    """El paciente cancela su turno."""
    if request.user.rol != 'paciente':
        return redirect('home')
    
    paciente = get_object_or_404(Paciente, usuario=request.user)
    turno = get_object_or_404(TurnoProfesional, id=turno_id, paciente=paciente)
    
    ahora = datetime.now()
    fecha_hora_turno = datetime.combine(turno.fecha, turno.hora_inicio)
    horas_restantes = (fecha_hora_turno - ahora).total_seconds() / 3600
    
    turno.estado = 'cancelado'
    turno.save()
    
    if horas_restantes < 24:
        messages.warning(request, f'Turno cancelado con menos de 24hs. Se descontará una sesión de obra social si corresponde.')
    else:
        messages.success(request, f'Turno del {turno.fecha.strftime("%d/%m/%Y")} a las {turno.hora_inicio.strftime("%H:%M")} cancelado.')
    
    return redirect('panel_paciente')


@login_required
def sacar_turno_paciente(request, profesional_id=None):
    if request.user.rol != 'paciente':
        return redirect('home')
    
    paciente = get_object_or_404(Paciente, usuario=request.user)
    hoy = date.today()
    
    # Obtener cliente SaaS de la sesión
    cliente_slug = request.session.get('cliente_slug')
    cliente = None
    if cliente_slug:
        try:
            cliente = ClienteSaaS.objects.get(slug=cliente_slug, activo=True)
        except ClienteSaaS.DoesNotExist:
            pass
    
    if profesional_id:
        profesional = get_object_or_404(Profesional, id=profesional_id, activo=True)
        # Verificar que pertenezca al cliente si es consultorio
        if cliente and cliente.tipo == 'consultorio':
            if cliente.establecimiento not in profesional.establecimientos.all():
                messages.error(request, 'Profesional no disponible en este consultorio.')
                return redirect('panel_paciente')
        return mostrar_formulario_paciente(request, paciente, profesional, hoy, cliente)
    
    # Filtrado según cliente
    if cliente:
        if cliente.tipo == 'consultorio':
            profesionales = Profesional.objects.filter(
                establecimientos=cliente.establecimiento, activo=True
            )
        else:  # profesional independiente
            profesionales = Profesional.objects.filter(
                id=cliente.profesional.id, activo=True
            )
    else:
        # Sin cliente en sesión, usar configuración del sistema
        config = ConfiguracionSistema.obtener()
        if config.modo == 'consultorio' and config.establecimiento_principal:
            # Modo consultorio: solo profesionales de ese consultorio
            profesionales = Profesional.objects.filter(
                establecimientos=config.establecimiento_principal,
                activo=True
            ).distinct()
        else:
            # Modo profesional independiente: todos los profesionales
            profesionales_ids = TurnoProfesional.objects.filter(
                paciente=paciente
            ).values_list('profesional_id', flat=True).distinct()
            
            profesionales = Profesional.objects.filter(
                Q(id__in=profesionales_ids) | Q(establecimientos__isnull=False),
                activo=True
            ).distinct()[:10]
    
    return render(request, 'pacientes/portal/elegir_profesional.html', {
        'paciente': paciente,
        'profesionales': profesionales,
        'cliente': cliente,
    })


def mostrar_formulario_paciente(request, paciente, profesional, hoy, cliente=None):
    """Muestra el formulario para que el paciente elija fecha y hora."""
    
    establecimiento_id = request.GET.get('establecimiento')
    establecimiento_seleccionado = None
    if establecimiento_id:
        establecimiento_seleccionado = get_object_or_404(Establecimiento, id=establecimiento_id)
        # Verificar que el establecimiento pertenezca al cliente si es consultorio
        if cliente and cliente.tipo == 'consultorio':
            if establecimiento_seleccionado != cliente.establecimiento:
                messages.error(request, 'Establecimiento no autorizado.')
                return redirect('panel_paciente')
    
    if request.method == 'POST':
        fecha_str = request.POST.get('fecha')
        hora_str = request.POST.get('hora')
        tipo_consulta = request.POST.get('tipo_consulta', '')
        establecimiento_id = request.POST.get('establecimiento')
        
        if not all([fecha_str, hora_str]):
            messages.error(request, 'Seleccioná fecha y hora.')
            return redirect('sacar_turno_paciente_profesional', profesional_id=profesional.id)
        
        if not establecimiento_id:
            messages.error(request, 'Seleccioná un consultorio.')
            return redirect('sacar_turno_paciente_profesional', profesional_id=profesional.id)
        
        try:
            fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
            hora = datetime.strptime(hora_str, '%H:%M').time()
        except ValueError:
            messages.error(request, 'Fecha u hora inválida.')
            return redirect('sacar_turno_paciente_profesional', profesional_id=profesional.id)
        
        if fecha < hoy:
            messages.error(request, 'No podés sacar turno para una fecha pasada.')
            return redirect('sacar_turno_paciente_profesional', profesional_id=profesional.id)
        
        establecimiento = get_object_or_404(Establecimiento, id=establecimiento_id)
        
        # Verificar que el establecimiento pertenezca al cliente si es consultorio
        if cliente and cliente.tipo == 'consultorio':
            if establecimiento != cliente.establecimiento:
                messages.error(request, 'Establecimiento no autorizado.')
                return redirect('panel_paciente')
        
        # Verificar disponibilidad con pacientes simultáneos
        turnos_en_horario = TurnoProfesional.objects.filter(
            profesional=profesional,
            establecimiento=establecimiento,
            fecha=fecha,
            hora_inicio=hora,
            estado__in=['pendiente', 'confirmado']
        ).count()
        
        agenda = Agenda.objects.filter(
            profesional=profesional,
            establecimiento=establecimiento,
            activo=True,
            fecha_inicio__lte=fecha
        ).first()
        
        max_simultaneos = agenda.pacientes_simultaneos if agenda else 1
        
        if turnos_en_horario >= max_simultaneos:
            messages.error(request, f'Horario completo (máx. {max_simultaneos} pacientes).')
            return redirect('sacar_turno_paciente_profesional', profesional_id=profesional.id)
        
        # Obtener duración
        duracion = 30
        if agenda:
            dia_semana = fecha.weekday()
            horario = HorarioAtencion.objects.filter(
                agenda=agenda,
                dia=dia_semana
            ).first()
            if horario:
                duracion = horario.duracion_turno
        
        hora_fin = (datetime.combine(fecha, hora) + timedelta(minutes=duracion)).time()
        
        TurnoProfesional.objects.create(
            profesional=profesional,
            establecimiento=establecimiento,
            paciente=paciente,
            fecha=fecha,
            hora_inicio=hora,
            hora_fin=hora_fin,
            estado='pendiente',
            tipo_consulta=tipo_consulta
        )
        
        messages.success(request, f'¡Turno reservado! Tu turno es el {fecha.strftime("%d/%m/%Y")} a las {hora_str} en {establecimiento.nombre} con {profesional.nombre_completo}.')
        return redirect('panel_paciente')
    
    # GET - Mostrar horarios disponibles
    dias_disponibles = []
    
    if establecimiento_seleccionado:
        agendas = Agenda.objects.filter(
            profesional=profesional,
            establecimiento=establecimiento_seleccionado,
            activo=True,
            fecha_inicio__lte=hoy + timedelta(days=30)
        )
    else:
        # Si hay cliente consultorio, filtrar por su establecimiento
        if cliente and cliente.tipo == 'consultorio':
            agendas = Agenda.objects.filter(
                profesional=profesional,
                establecimiento=cliente.establecimiento,
                activo=True,
                fecha_inicio__lte=hoy + timedelta(days=30)
            )
        else:
            agendas = Agenda.objects.filter(
                profesional=profesional,
                activo=True,
                fecha_inicio__lte=hoy + timedelta(days=30)
            )
    
    agenda = agendas.first()
    
    if agenda:
        max_simultaneos = agenda.pacientes_simultaneos if agenda else 1
        establecimiento_agenda = agenda.establecimiento
        
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
                        ocupados = TurnoProfesional.objects.filter(
                            profesional=profesional,
                            establecimiento=establecimiento_agenda,
                            fecha=fecha,
                            hora_inicio=hora_actual,
                            estado__in=['pendiente', 'confirmado']
                        ).count()
                        
                        if ocupados < max_simultaneos:
                            slots.append(hora_actual.strftime('%H:%M'))
                    
                    hora_actual = hora_fin_slot
                
                if slots:
                    dias_disponibles.append({
                        'fecha': fecha,
                        'fecha_str': fecha.strftime('%Y-%m-%d'),
                        'nombre_dia': fecha.strftime('%A'),
                        'slots': slots
                    })
    
    return render(request, 'pacientes/portal/sacar_turno.html', {
        'paciente': paciente,
        'profesional': profesional,
        'dias_disponibles': dias_disponibles,
        'hoy': hoy,
        'establecimiento_seleccionado': establecimiento_seleccionado,
        'cliente': cliente,
    })