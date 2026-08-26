from decimal import Decimal
import threading

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Count, Sum
from datetime import date, timedelta, datetime
from django.http import HttpResponse, JsonResponse
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A5
from reportlab.lib.units import cm
from openpyxl import Workbook
from establecimientos.models import Establecimiento
from obras_sociales.models import Plan
from .models import TurnoProfesional, ArchivoTurno
from profesionales.models import Profesional
from pacientes.models import Paciente, PacienteObraSocial
from agendas.models import Agenda, HorarioAtencion, BloqueoAgenda
from historias_clinicas.models import HistoriaClinica, Evolucion, ArchivoClinico
from .google_calendar import GoogleCalendarManager
from datetime import datetime
from core_app.models import ClienteSaaS

def _get_establecimiento_activo(request, profesional):
    """
    Devuelve el establecimiento correspondiente al cliente activo en la sesión,
    siempre que el profesional trabaje allí. Si no hay cliente activo, devuelve None
    (lo que significa que se deben mostrar todos los establecimientos).
    """
    slug = request.session.get('cliente_slug')
    if slug:
        try:
            cliente = ClienteSaaS.objects.get(slug=slug, activo=True)
            if cliente.establecimiento in profesional.establecimientos.all():
                return cliente.establecimiento
        except ClienteSaaS.DoesNotExist:
            pass
    return None


def marcar_turnos_vencidos(profesional=None):
    """
    Marca como 'no_asistio' los turnos de hoy que ya pasaron 30 min de su hora de inicio,
    y también cualquier turno de días anteriores que haya quedado pendiente/confirmado.
    """
    ahora = datetime.now()
    hoy = ahora.date()
    hora_limite = (ahora - timedelta(minutes=30)).time()

    # 1. Turnos de HOY que vencieron
    filtro_hoy = {
        'fecha': hoy,
        'estado__in': ['pendiente', 'confirmado'],
        'hora_inicio__lte': hora_limite,
        'no_asistio_automatico': False,
    }
    if profesional:
        filtro_hoy['profesional'] = profesional

    # 2. Turnos de días ANTERIORES que todavía están pendientes/confirmados
    filtro_pasados = {
        'fecha__lt': hoy,
        'estado__in': ['pendiente', 'confirmado'],
        'no_asistio_automatico': False,
    }
    if profesional:
        filtro_pasados['profesional'] = profesional

    # Unimos los dos conjuntos de turnos
    from django.db.models import Q
    turnos_vencidos = TurnoProfesional.objects.filter(
        Q(**filtro_hoy) | Q(**filtro_pasados)
    )

    for turno in turnos_vencidos:
        turno.estado = 'no_asistio'
        turno.no_asistio_automatico = True

        # Descontar sesión de OS si corresponde
        os_paciente = PacienteObraSocial.objects.filter(
            paciente=turno.paciente, activa=True,
            profesional=turno.profesional, sesiones_restantes__gt=0
        ).first()
        if os_paciente:
            os_paciente.sesiones_restantes -= 1
            os_paciente.save()
            turno.sesion_descontada = True

        turno.save()


# ============ GOOGLE CALENDAR (funciones auxiliares) ============


def crear_evento_google(turno):
    """Crea un evento en Google Calendar."""
    try:
        gcal = GoogleCalendarManager()
        fecha_str = turno.fecha.strftime('%Y-%m-%d')
        start_time = f"{fecha_str}T{turno.hora_inicio.strftime('%H:%M:%S')}"
        end_time = f"{fecha_str}T{turno.hora_fin.strftime('%H:%M:%S')}"
        summary = f"Turno: {turno.paciente.nombre_completo} - {turno.profesional.nombre_completo}"
        description = f"""
Paciente: {turno.paciente.nombre_completo}
DNI: {turno.paciente.dni}
Teléfono: {turno.paciente.telefono}
Tipo: {turno.tipo_consulta or '—'}
Consultorio: {turno.establecimiento.nombre if turno.establecimiento else '—'}
        """
        location = turno.establecimiento.direccion if turno.establecimiento else ''
        attendees = []
        if turno.paciente.email:
            attendees.append(turno.paciente.email)
        if turno.profesional.email:
            attendees.append(turno.profesional.email)
        event = gcal.create_event(
            summary=summary, start_time=start_time, end_time=end_time,
            timezone="America/Argentina/Salta", attendees=attendees,
            description=description, location=location
        )
        if event and 'id' in event:
            turno.google_event_id = event['id']
            turno.save(update_fields=['google_event_id'])
            return True
    except Exception as e:
        print(f"❌ Error Google Calendar: {e}")
    return False


def eliminar_evento_google(turno):
    """Elimina el evento de Google Calendar."""
    if not turno.google_event_id:
        return False
    try:
        gcal = GoogleCalendarManager()
        return gcal.delete_event(turno.google_event_id)
    except:
        return False


# ============ PANEL PROFESIONAL ============
@login_required
def panel_profesional(request):
    if request.user.rol not in ['profesional', 'secretaria']:
        messages.error(request, 'No tenés acceso a esta sección.')
        return redirect('home')
    
    if request.user.rol == 'secretaria':
        # La secretaria sigue con su lógica actual
        establecimiento_id = request.GET.get('establecimiento')
        profesional_id = request.GET.get('profesional')
        if establecimiento_id and profesional_id:
            profesional = get_object_or_404(Profesional, id=profesional_id)
        elif establecimiento_id:
            profesional = Profesional.objects.filter(
                establecimientos__id=establecimiento_id, activo=True
            ).first()
        else:
            profesional = Profesional.objects.filter(
                establecimientos=request.user.establecimiento, activo=True
            ).first()
        if not profesional:
            messages.error(request, 'No hay profesionales disponibles.')
            return redirect('panel_secretaria')
        establecimientos = request.user.establecimiento.__class__.objects.filter(
            profesionales__isnull=False
        ).distinct() if request.user.establecimiento else []
        profesionales_consultorio = Profesional.objects.filter(
            establecimientos=request.user.establecimiento, activo=True
        )
        establecimiento_filtro = request.user.establecimiento  # la secretaria siempre ve su establecimiento
    else:
        profesional = get_object_or_404(Profesional, usuario=request.user)
        establecimientos = profesional.establecimientos.all()
        profesionales_consultorio = None
        establecimiento_filtro = _get_establecimiento_activo(request, profesional)

    hoy = date.today()
    marcar_turnos_vencidos(profesional=profesional)

    # Turnos de hoy (filtrados si corresponde)
    turnos_hoy_qs = TurnoProfesional.objects.filter(profesional=profesional, fecha=hoy)
    if establecimiento_filtro:
        turnos_hoy_qs = turnos_hoy_qs.filter(establecimiento=establecimiento_filtro)
    turnos_hoy_qs = turnos_hoy_qs.order_by('hora_inicio')

    turnos_hoy = list(turnos_hoy_qs)
    ahora = datetime.now()
    for turno in turnos_hoy:
        if turno.estado == 'no_asistio' and turno.no_asistio_automatico:
            fecha_hora_inicio = datetime.combine(turno.fecha, turno.hora_inicio)
            limite = fecha_hora_inicio + timedelta(minutes=60)
            turno.puede_reactivar = (ahora <= limite)
        else:
            turno.puede_reactivar = False

    manana = hoy + timedelta(days=1)
    proxima_semana = hoy + timedelta(days=7)
    proximos_turnos = TurnoProfesional.objects.filter(
        profesional=profesional,
        fecha__range=[manana, proxima_semana],
        estado__in=['pendiente', 'confirmado']
    )
    if establecimiento_filtro:
        proximos_turnos = proximos_turnos.filter(establecimiento=establecimiento_filtro)
    proximos_turnos = proximos_turnos.order_by('fecha', 'hora_inicio')[:10]

    hay_mas_proximos = TurnoProfesional.objects.filter(
        profesional=profesional,
        fecha__range=[manana, proxima_semana],
        estado__in=['pendiente', 'confirmado']
    )
    if establecimiento_filtro:
        hay_mas_proximos = hay_mas_proximos.filter(establecimiento=establecimiento_filtro)
    hay_mas_proximos = hay_mas_proximos.count() > 10

    sesiones_por_turno = {}
    for turno in turnos_hoy_qs:
        os_paciente = turno.paciente.mis_obras_sociales.filter(
            profesional=turno.profesional, activa=True
        ).first()
        sesiones_por_turno[turno.id] = os_paciente

    mostrar_consultorio = profesional.establecimientos.count() > 1 and not establecimiento_filtro

    contexto = {
        'profesional': profesional,
        'hoy': hoy,
        'turnos_hoy': turnos_hoy,
        'proximos_turnos': proximos_turnos,
        'hay_mas_proximos': hay_mas_proximos,
        'total_hoy': turnos_hoy_qs.count(),
        'sesiones_por_turno': sesiones_por_turno,
        'confirmados_hoy': turnos_hoy_qs.filter(estado='confirmado').count(),
        'pendientes_hoy': turnos_hoy_qs.filter(estado='pendiente').count(),
        'completados_hoy': turnos_hoy_qs.filter(estado='completado').count(),
        'mostrar_consultorio': mostrar_consultorio,
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
def pasar_a_sala(request, turno_id):
    turno = get_object_or_404(TurnoProfesional, id=turno_id)
    if request.user.rol not in ['profesional', 'secretaria']:
        return redirect('home')
    
    turno.estado = 'en_sala'
    turno.save()
    messages.info(request, f'{turno.paciente.nombre_completo} ahora está en sala de espera.')
    
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

    from .notificaciones import notificar_cancelacion_turno
    notificar_cancelacion_turno(turno, cancelado_por='profesional')
    
    # Eliminar evento de Google Calendar
    try:
        threading.Thread(target=eliminar_evento_google, args=(turno,)).start()
    except:
        pass
    
    messages.warning(request, f'Turno de {turno.paciente.nombre_completo} cancelado.')
    
    if request.user.rol == 'secretaria':
        return redirect('panel_secretaria')
    return redirect('panel_profesional')


@login_required
def completar_turno(request, turno_id):
    turno = get_object_or_404(TurnoProfesional, id=turno_id)
    if request.user.rol not in ['profesional', 'secretaria']:
        messages.error(request, 'No tenés permiso.')
        return redirect('home')
    
    turno.estado = 'completado'
    paciente = turno.paciente
    
    # Dentro de completar_turno, reemplazar el bloque de descuento actual por esto:
    if not turno.sesion_descontada:
        os_paciente = PacienteObraSocial.objects.filter(
            paciente=paciente,
            activa=True,
            profesional=turno.profesional
        ).first()
        if os_paciente and os_paciente.sesiones_restantes is not None and os_paciente.sesiones_restantes > 0:
            os_paciente.sesiones_restantes -= 1
            os_paciente.save()
            turno.sesion_descontada = True
    else:
        # Ya estaba descontada (por inasistencia anterior), no hacer nada
        pass
    
    if paciente.plan_obra_social:
        plan = paciente.plan_obra_social
        if plan.coseguro_fijo and plan.coseguro_fijo > 0:
            turno.monto_coseguro = plan.coseguro_fijo
        elif plan.coseguro_porcentaje and plan.coseguro_porcentaje > 0:
            turno.monto_coseguro = 0
    
    turno.save()


    from .notificaciones import notificar_turno_completado
    notificar_turno_completado(turno)
    # Eliminar evento de Google Calendar
    try:
        threading.Thread(target=eliminar_evento_google, args=(turno,)).start()
    except:
        pass

    return redirect('cargar_evolucion', turno_id=turno.id)
    
@login_required
def cobrar_turno(request, turno_id):
    turno = get_object_or_404(TurnoProfesional, id=turno_id)
    
    if request.user.rol not in ['profesional', 'secretaria']:
        return redirect('home')
    
    paciente = turno.paciente
    
    if request.user.rol == 'profesional':
        profesional = get_object_or_404(Profesional, usuario=request.user)
    else:
        profesional = None

    # Obtener todas las obras sociales activas del paciente para este profesional
    obras_sociales_activas = PacienteObraSocial.objects.filter(
        paciente=paciente,
        activa=True,
        profesional=profesional  # se filtra por el profesional que está cobrando
    ).select_related('obra_social', 'plan')

    # Por defecto, seleccionamos la primera OS activa (o ninguna)
    obra_social_seleccionada = None
    plan_seleccionado = None

    if request.method == 'POST':
        monto_total = request.POST.get('monto_total', '')
        monto_os = request.POST.get('monto_os', '')
        monto_coseguro = request.POST.get('monto_coseguro', '')
        os_id = request.POST.get('obra_social')           # ID de PacienteObraSocial
        plan_id = request.POST.get('plan')                # ID de Plan (opcional)

        # Guardar montos
        if monto_total:
            turno.monto_total = Decimal(monto_total)
        if monto_os:
            turno.monto_os = Decimal(monto_os)
        
        # Solo guardamos coseguro si se seleccionó una OS
        if os_id and monto_coseguro:
            turno.monto_coseguro = Decimal(monto_coseguro)
        else:
            turno.monto_coseguro = None

        # Asociar la obra social elegida al turno (campo existente)
        if os_id:
            try:
                os_paciente = PacienteObraSocial.objects.get(id=os_id, paciente=paciente)
                turno.obra_social = os_paciente.obra_social
                # Si se eligió un plan, podemos guardarlo en el paciente o usarlo para cálculos
                if plan_id:
                    plan = Plan.objects.get(id=plan_id, obra_social=os_paciente.obra_social)
                    paciente.plan_obra_social = plan
                    paciente.save()
            except PacienteObraSocial.DoesNotExist:
                pass
        else:
            turno.obra_social = None
            paciente.plan_obra_social = None
            paciente.save()

        turno.save()

        # Calcular coseguro automático si hay OS y no se especificó coseguro
        if turno.obra_social and turno.monto_total and turno.monto_os and not turno.monto_coseguro:
            turno.monto_coseguro = turno.monto_total - turno.monto_os
            turno.save()

        messages.success(request, '✅ Cobro registrado correctamente.')
        return redirect('panel_profesional')

    # GET
    context = {
        'turno': turno,
        'paciente': paciente,
        'profesional': profesional,
        'obras_sociales_activas': obras_sociales_activas,   # lista de PacienteObraSocial
    }
    return render(request, 'turnos_profesionales/cobrar_turno.html', context)

@login_required
def no_asistio_turno(request, turno_id):
    turno = get_object_or_404(TurnoProfesional, id=turno_id)
    if request.user.rol not in ['profesional', 'secretaria']:
        messages.error(request, 'No tenés permiso.')
        return redirect('panel_profesional')

    turno.estado = 'no_asistio'
    turno.no_asistio_automatico = False  # fue manual

    # Descontar sesión si no se había descontado antes
    if not turno.sesion_descontada:
        os_paciente = PacienteObraSocial.objects.filter(
            paciente=turno.paciente,
            activa=True,
            profesional=turno.profesional,
            sesiones_restantes__gt=0,
        ).first()
        if os_paciente:
            os_paciente.sesiones_restantes -= 1
            os_paciente.save()
            turno.sesion_descontada = True

    turno.save()

    from .notificaciones import notificar_no_asistio
    notificar_no_asistio(turno)

    # Eliminar evento de Google Calendar
    try:
        threading.Thread(target=eliminar_evento_google, args=(turno,)).start()
    except:
        pass

    messages.warning(request, f'{turno.paciente.nombre_completo} no asistió.')

    if request.user.rol == 'secretaria':
        return redirect('panel_secretaria')
    return redirect('panel_profesional')

# ============ CARGA DE EVOLUCIÓN ============

@login_required
def cargar_evolucion(request, turno_id):
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
        medicacion_recetada = request.POST.get('medicacion_recetada', '')
        
        if not motivo:
            messages.error(request, 'El motivo de consulta es obligatorio.')
            return redirect('cargar_evolucion', turno_id=turno.id)
        
        evolucion = Evolucion.objects.create(
            historia_clinica=historia, turno=turno, profesional=profesional,
            motivo_consulta=motivo, diagnostico=diagnostico,
            tratamiento_realizado=tratamiento, indicaciones=indicaciones,
            medicacion_recetada=medicacion_recetada,
            proximo_control=proximo_control if proximo_control else None
        )
        
        archivos = request.FILES.getlist('archivos')
        descripcion_archivo = request.POST.get('descripcion_archivo', '')
        for archivo in archivos:
            ArchivoClinico.objects.create(
                evolucion=evolucion, archivo=archivo,
                descripcion=descripcion_archivo, tipo='foto'
            )
        
        if proximo_control:
            try:
                fecha_control = datetime.strptime(proximo_control, '%Y-%m-%d').date()
                hora_preferida = request.POST.get('proximo_control_hora', '')
                
                agenda = Agenda.objects.filter(
                    profesional=profesional, activo=True,
                    fecha_inicio__lte=fecha_control
                ).filter(Q(fecha_fin__isnull=True) | Q(fecha_fin__gte=fecha_control)).first()
                
                if agenda:
                    dia_semana = fecha_control.weekday()
                    horario = HorarioAtencion.objects.filter(agenda=agenda, dia=dia_semana).first()
                    
                    if horario:
                        slot_encontrado = None
                        
                        if hora_preferida:
                            try:
                                hora_pref = datetime.strptime(hora_preferida, '%H:%M').time()
                                ocupado = TurnoProfesional.objects.filter(
                                    profesional=profesional, fecha=fecha_control,
                                    hora_inicio=hora_pref, estado__in=['pendiente', 'confirmado']
                                ).exists()
                                if not ocupado:
                                    if horario.hora_inicio <= hora_pref and (
                                        datetime.combine(fecha_control, hora_pref) + 
                                        timedelta(minutes=horario.duracion_turno)
                                    ).time() <= horario.hora_fin:
                                        slot_encontrado = hora_pref
                            except:
                                pass
                        
                        if not slot_encontrado:
                            hora_actual = horario.hora_inicio
                            while hora_actual < horario.hora_fin:
                                ocupado = TurnoProfesional.objects.filter(
                                    profesional=profesional, fecha=fecha_control,
                                    hora_inicio=hora_actual, estado__in=['pendiente', 'confirmado']
                                ).exists()
                                if not ocupado:
                                    slot_encontrado = hora_actual
                                    break
                                hora_actual = (datetime.combine(fecha_control, hora_actual) + 
                                              timedelta(minutes=horario.duracion_turno)).time()
                        
                        if slot_encontrado:
                            hora_fin_control = (datetime.combine(fecha_control, slot_encontrado) + 
                                               timedelta(minutes=horario.duracion_turno)).time()
                            nuevo_turno = TurnoProfesional.objects.create(
                                profesional=profesional,
                                establecimiento=turno.establecimiento,
                                paciente=turno.paciente,
                                fecha=fecha_control, hora_inicio=slot_encontrado,
                                hora_fin=hora_fin_control, estado='pendiente',
                                tipo_consulta='Control',
                                notas_internas=f'Turno automático del {turno.fecha.strftime("%d/%m/%Y")}'
                            )
                            # Google Calendar
                            try:
                                threading.Thread(target=crear_evento_google, args=(nuevo_turno,)).start()
                            except:
                                pass
                            messages.success(request, 
                                f'✅ Turno de control creado para el {fecha_control.strftime("%d/%m/%Y")} a las {slot_encontrado.strftime("%H:%M")}.')
                        else:
                            messages.info(request, 
                                f'⚠️ No se encontraron horarios libres para el {fecha_control.strftime("%d/%m/%Y")}.')
            except:
                pass
        
        messages.success(request, '✅ Evolución guardada. Completá la ficha del paciente.')
        return redirect(f'/pacientes/{turno.paciente.id}/?turno_id={turno.id}')
    
    return render(request, 'turnos_profesionales/cargar_evolucion.html', {
        'profesional': profesional, 'turno': turno, 'historia': historia
    })


@login_required
def api_calendario_proximo_control(request, turno_id):
    turno = get_object_or_404(TurnoProfesional, id=turno_id)
    profesional = turno.profesional
    establecimiento = turno.establecimiento

    establecimiento = turno.establecimiento
    if not establecimiento:
        establecimiento = profesional.establecimientos.first()
    if not establecimiento:
        return JsonResponse({'dias': []})

    # Verificar que el profesional logueado sea el dueño del turno
    if request.user.rol != 'profesional' or request.user != profesional.usuario:
        return JsonResponse({'error': 'No autorizado'}, status=403)

    hoy = date.today()
    agenda = Agenda.objects.filter(
        profesional=profesional,
        establecimiento=establecimiento,
        activo=True
    ).first()

    if not agenda:
        return JsonResponse({'dias': []})

    max_simultaneos = agenda.pacientes_simultaneos if agenda.pacientes_simultaneos else 1
    bloqueos = BloqueoAgenda.objects.filter(agenda=agenda, activo=True)
    dias = []

    for i in range(30):
        fecha = hoy + timedelta(days=i)
        dia_semana = fecha.weekday()
        horario = HorarioAtencion.objects.filter(agenda=agenda, dia=dia_semana).first()
        if not horario:
            continue

        # Día completamente bloqueado
        dia_bloqueado = bloqueos.filter(
            fecha=fecha, hora_inicio__isnull=True, hora_fin__isnull=True
        ).exists()
        if dia_bloqueado:
            continue

        slots = []
        hora_actual = horario.hora_inicio
        while hora_actual < horario.hora_fin:
            hora_fin_slot = (datetime.combine(fecha, hora_actual) + timedelta(minutes=horario.duracion_turno)).time()
            if hora_fin_slot <= horario.hora_fin:
                slot_bloqueado = bloqueos.filter(
                    fecha=fecha,
                    hora_inicio__lte=hora_actual,
                    hora_fin__gte=hora_fin_slot
                ).exists()
                if not slot_bloqueado:
                    ocupados = TurnoProfesional.objects.filter(
                        profesional=profesional,
                        establecimiento=establecimiento,
                        fecha=fecha,
                        hora_inicio=hora_actual,
                        estado__in=['pendiente', 'confirmado']
                    ).count()
                    if ocupados < max_simultaneos:
                        slots.append(hora_actual.strftime('%H:%M'))
            hora_actual = hora_fin_slot

        if slots:
            dias.append({
                'fecha_str': fecha.strftime('%Y-%m-%d'),
                'slots': slots
            })

    return JsonResponse({'dias': dias})

# ============ ASIGNAR TURNO ============
@login_required
def asignar_turno(request, paciente_id):
    if request.user.rol not in ['profesional', 'secretaria']:
        return redirect('home')
    
    if request.user.rol == 'secretaria':
        profesional_id = request.GET.get('profesional')
        if profesional_id:
            profesional = get_object_or_404(Profesional, id=profesional_id)
        else:
            profesional = Profesional.objects.filter(
                establecimientos=request.user.establecimiento, activo=True
            ).first()
        establecimiento_filtro = request.user.establecimiento
    else:
        profesional = get_object_or_404(Profesional, usuario=request.user)
        establecimiento_filtro = _get_establecimiento_activo(request, profesional)
    
    if not profesional:
        messages.error(request, 'No hay profesionales disponibles.')
        return redirect('panel_secretaria' if request.user.rol == 'secretaria' else 'home')
    
    paciente = get_object_or_404(Paciente, id=paciente_id)
    hoy = date.today()

    obra_social_activa = PacienteObraSocial.objects.filter(
        paciente=paciente, profesional=profesional, activa=True
    ).first()
    
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
        
        establecimiento = None
        establecimiento_id = request.POST.get('establecimiento')
        if establecimiento_id:
            establecimiento = get_object_or_404(Establecimiento, id=establecimiento_id)
        else:
            # Usa el establecimiento filtrado, o el primero si no hay filtro
            establecimiento = establecimiento_filtro if establecimiento_filtro else profesional.establecimientos.first()
        
        turnos_en_horario = TurnoProfesional.objects.filter(
            profesional=profesional, fecha=fecha, hora_inicio=hora,
            estado__in=['pendiente', 'confirmado']
        )
        if establecimiento_filtro:
            turnos_en_horario = turnos_en_horario.filter(establecimiento=establecimiento)
        
        agenda = Agenda.objects.filter(profesional=profesional, activo=True, fecha_inicio__lte=fecha)
        if establecimiento_filtro:
            agenda = agenda.filter(establecimiento=establecimiento_filtro)
        agenda = agenda.first()
        max_simultaneos = agenda.pacientes_simultaneos if agenda else 1
        
        if turnos_en_horario.count() >= max_simultaneos:
            messages.error(request, f'Horario completo (máx. {max_simultaneos} pacientes).')
            return redirect('asignar_turno', paciente_id=paciente.id)
        
        duracion = 30
        if agenda:
            dia_semana = fecha.weekday()
            horario = HorarioAtencion.objects.filter(agenda=agenda, dia=dia_semana).first()
            if horario:
                duracion = horario.duracion_turno
        
        hora_fin = (datetime.combine(fecha, hora) + timedelta(minutes=duracion)).time()
        
        turno = TurnoProfesional.objects.create(
            profesional=profesional, establecimiento=establecimiento,
            paciente=paciente, fecha=fecha, hora_inicio=hora,
            hora_fin=hora_fin, estado='pendiente',
            tipo_consulta=tipo_consulta, notas_internas=notas
        )
        
        archivo = request.FILES.get('archivo')
        if archivo:
            turno.archivo = archivo
            turno.save()
        
        try:
            threading.Thread(target=crear_evento_google, args=(turno,)).start()
        except:
            pass

        from .notificaciones import notificar_turno_asignado
        notificar_turno_asignado(turno)
        
        messages.success(request, f'Turno asignado a {paciente.nombre_completo} el {fecha.strftime("%d/%m/%Y")} a las {hora_str}.')
        
        if request.user.rol == 'secretaria':
            return redirect('panel_secretaria')
        return redirect('panel_profesional')
    
    # GET
    dias_disponibles = []
    agenda = Agenda.objects.filter(profesional=profesional, activo=True, fecha_inicio__lte=hoy + timedelta(days=30))
    if establecimiento_filtro:
        agenda = agenda.filter(establecimiento=establecimiento_filtro)
    agenda = agenda.first()
    max_simultaneos = agenda.pacientes_simultaneos if agenda else 1
    
    if agenda:
        for i in range(30):
            fecha = hoy + timedelta(days=i)
            dia_semana = fecha.weekday()
            horario = HorarioAtencion.objects.filter(agenda=agenda, dia=dia_semana).first()
            if horario:
                hora_actual = horario.hora_inicio
                slots = []
                while hora_actual < horario.hora_fin:
                    hora_fin_slot = (datetime.combine(fecha, hora_actual) + timedelta(minutes=horario.duracion_turno)).time()
                    if hora_fin_slot <= horario.hora_fin:
                        ocupados = TurnoProfesional.objects.filter(
                            profesional=profesional, fecha=fecha,
                            hora_inicio=hora_actual, estado__in=['pendiente', 'confirmado']
                        )
                        if establecimiento_filtro:
                            ocupados = ocupados.filter(establecimiento=establecimiento_filtro)
                        if ocupados.count() < max_simultaneos:
                            slots.append(hora_actual.strftime('%H:%M'))
                    hora_actual = hora_fin_slot
                if slots:
                    dias_disponibles.append({
                        'fecha': fecha, 'fecha_str': fecha.strftime('%Y-%m-%d'),
                        'nombre_dia': fecha.strftime('%A'), 'slots': slots
                    })
    
    profesionales_consultorio = None
    if request.user.rol == 'secretaria':
        profesionales_consultorio = Profesional.objects.filter(
            establecimientos=request.user.establecimiento, activo=True
        )
    
    return render(request, 'turnos_profesionales/asignar_turno.html', {
        'profesional': profesional, 'paciente': paciente,
        'dias_disponibles': dias_disponibles, 'hoy': hoy,
        'profesionales_consultorio': profesionales_consultorio,
        'max_simultaneos': max_simultaneos,
        'obra_social_activa': obra_social_activa,
    })


# ============ EDITAR TURNO ============
@login_required
def editar_turno(request, turno_id):
    if request.user.rol not in ['profesional', 'secretaria']:
        return redirect('home')
    
    turno = get_object_or_404(TurnoProfesional, id=turno_id)
    
    if request.user.rol == 'secretaria':
        profesional = turno.profesional
        establecimiento_filtro = request.user.establecimiento
    else:
        profesional = get_object_or_404(Profesional, usuario=request.user)
        if request.user != turno.profesional.usuario:
            messages.error(request, 'No tenés permiso.')
            return redirect('panel_profesional')
        establecimiento_filtro = _get_establecimiento_activo(request, profesional)
    
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
        
        # Verificar conflictos (solo turnos en el mismo establecimiento)
        existe = TurnoProfesional.objects.filter(
            profesional=profesional, fecha=fecha, hora_inicio=hora,
            estado__in=['pendiente', 'confirmado']
        ).exclude(id=turno.id)
        if establecimiento_filtro:
            existe = existe.filter(establecimiento=establecimiento_filtro)
        if existe.exists():
            messages.error(request, 'Ese horario ya está ocupado.')
            return redirect('editar_turno_pro', turno_id=turno.id)
        
        turno.fecha = fecha
        turno.hora_inicio = hora
        turno.estado = estado
        turno.tipo_consulta = tipo_consulta
        turno.notas_internas = notas
        
        # Duración del turno basada en la agenda correspondiente
        agenda = Agenda.objects.filter(profesional=profesional, activo=True, fecha_inicio__lte=fecha)
        if establecimiento_filtro:
            agenda = agenda.filter(establecimiento=establecimiento_filtro)
        agenda = agenda.filter(Q(fecha_fin__isnull=True) | Q(fecha_fin__gte=fecha)).first()
        duracion = 30
        if agenda:
            horario_atencion = HorarioAtencion.objects.filter(agenda=agenda, dia=fecha.weekday()).first()
            if horario_atencion:
                duracion = horario_atencion.duracion_turno
        
        turno.hora_fin = (datetime.combine(fecha, hora) + timedelta(minutes=duracion)).time()
        turno.save()
        
        archivos = request.FILES.getlist('archivos')
        descripcion_archivo = request.POST.get('descripcion_archivo', '')
        for archivo in archivos:
            ArchivoTurno.objects.create(turno=turno, archivo=archivo, descripcion=descripcion_archivo)
        
        try:
            threading.Thread(target=eliminar_evento_google, args=(turno,)).start()
            threading.Thread(target=crear_evento_google, args=(turno,)).start()
        except:
            pass
        
        messages.success(request, 'Turno actualizado correctamente.')
        if request.user.rol == 'secretaria':
            return redirect('panel_secretaria')
        return redirect('panel_profesional')
    
    # GET
    dias_disponibles = []
    agenda = Agenda.objects.filter(profesional=profesional, activo=True, fecha_inicio__lte=hoy + timedelta(days=30))
    if establecimiento_filtro:
        agenda = agenda.filter(establecimiento=establecimiento_filtro)
    agenda = agenda.first()
    if agenda:
        for i in range(30):
            fecha = hoy + timedelta(days=i)
            horario = HorarioAtencion.objects.filter(agenda=agenda, dia=fecha.weekday()).first()
            if horario:
                hora_actual = horario.hora_inicio
                slots = []
                while hora_actual < horario.hora_fin:
                    hora_fin_slot = (datetime.combine(fecha, hora_actual) + timedelta(minutes=horario.duracion_turno)).time()
                    if hora_fin_slot <= horario.hora_fin:
                        ocupado = TurnoProfesional.objects.filter(
                            profesional=profesional, fecha=fecha, hora_inicio=hora_actual,
                            estado__in=['pendiente', 'confirmado']
                        ).exclude(id=turno.id)
                        if establecimiento_filtro:
                            ocupado = ocupado.filter(establecimiento=establecimiento_filtro)
                        if not ocupado.exists() or (fecha == turno.fecha and hora_actual == turno.hora_inicio):
                            slots.append(hora_actual.strftime('%H:%M'))
                    hora_actual = hora_fin_slot
                if slots:
                    dias_disponibles.append({
                        'fecha': fecha, 'fecha_str': fecha.strftime('%Y-%m-%d'),
                        'nombre_dia': fecha.strftime('%A'), 'slots': slots
                    })
    
    return render(request, 'turnos_profesionales/editar_turno.html', {
        'profesional': profesional, 'turno': turno,
        'dias_disponibles': dias_disponibles, 'hoy': hoy
    })


# ============ CALENDARIO SEMANAL ============
@login_required
def calendario_semanal(request):
    if request.user.rol not in ['profesional', 'secretaria']:
        return redirect('home')
    
    if request.user.rol == 'secretaria':
        profesional_id = request.GET.get('profesional')
        if profesional_id:
            profesional = get_object_or_404(Profesional, id=profesional_id)
        else:
            profesional = Profesional.objects.filter(
                establecimientos=request.user.establecimiento, activo=True, atiende_por_orden=False
            ).first()
            if not profesional:
                messages.error(request, 'No hay profesionales con turnos programados.')
                return redirect('panel_secretaria')
        establecimiento_filtro = request.user.establecimiento
    else:
        profesional = get_object_or_404(Profesional, usuario=request.user)
        establecimiento_filtro = _get_establecimiento_activo(request, profesional)

    fecha_str = request.GET.get('fecha')
    if fecha_str:
        try:
            fecha_base = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        except ValueError:
            fecha_base = date.today()
    else:
        fecha_base = date.today()

    hoy = date.today()
    lunes = fecha_base - timedelta(days=fecha_base.weekday())
    dias_semana = []
    nombres_dias = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']

    agendas = Agenda.objects.filter(profesional=profesional, activo=True)
    if establecimiento_filtro:
        agendas = agendas.filter(establecimiento=establecimiento_filtro)
    agendas = agendas.select_related('establecimiento')

    marcar_turnos_vencidos(profesional=profesional)

    for i in range(7):
        dia = lunes + timedelta(days=i)
        turnos_dia = TurnoProfesional.objects.filter(profesional=profesional, fecha=dia)
        if establecimiento_filtro:
            turnos_dia = turnos_dia.filter(establecimiento=establecimiento_filtro)
        turnos_dia = turnos_dia.order_by('hora_inicio')

        horarios_por_consultorio = {}
        dia_bloqueado = False
        bloqueos_dia = []

        for agenda in agendas:
            if agenda.fecha_inicio <= dia and (agenda.fecha_fin is None or agenda.fecha_fin >= dia):
                bloqueos = BloqueoAgenda.objects.filter(agenda=agenda, fecha=dia, activo=True)
                bloqueos_dia.extend(bloqueos)
                if any(b.hora_inicio is None and b.hora_fin is None for b in bloqueos):
                    dia_bloqueado = True
                est_nombre = agenda.establecimiento.nombre
                if est_nombre not in horarios_por_consultorio:
                    horarios_por_consultorio[est_nombre] = []
                horarios = HorarioAtencion.objects.filter(agenda=agenda, dia=dia.weekday())
                for h in horarios:
                    hora_actual = h.hora_inicio
                    while hora_actual < h.hora_fin:
                        hora_fin_slot = (datetime.combine(dia, hora_actual) + timedelta(minutes=h.duracion_turno)).time()
                        if hora_fin_slot <= h.hora_fin:
                            slot_bloqueado = any(
                                b.hora_inicio and b.hora_fin and hora_actual >= b.hora_inicio and hora_fin_slot <= b.hora_fin
                                for b in bloqueos
                            )
                            if not slot_bloqueado:
                                turnos_en_horario = [t for t in turnos_dia if t.hora_inicio == hora_actual]
                                # Contamos cuántos están activos (pendiente/confirmado)
                                activos = [t for t in turnos_en_horario if t.estado in ['pendiente', 'confirmado']]
                                cantidad_ocupados = len(activos)
                                capacidad = agenda.pacientes_simultaneos

                                # 1) Agregar los slots ocupados (solo los activos o también los no activos?)
                                # Normalmente mostramos todos los turnos, incluso los completados/cancelados
                                for turno in turnos_en_horario:
                                    archivo_url = turno.archivo.url if turno.archivo else ''
                                    slot_data = {
                                        'hora_inicio': hora_actual,
                                        'hora_fin': hora_fin_slot,
                                        'turno': turno,
                                        'disponible': False,
                                        'lugares_restantes': 0,
                                        'puede_reactivar': False,
                                        'archivo_url': archivo_url,
                                    }
                                    if turno.estado == 'no_asistio' and turno.no_asistio_automatico:
                                        ahora = datetime.now()
                                        fecha_hora_inicio = datetime.combine(turno.fecha, turno.hora_inicio)
                                        limite = fecha_hora_inicio + timedelta(minutes=60)
                                        if ahora <= limite:
                                            slot_data['puede_reactivar'] = True
                                    horarios_por_consultorio[est_nombre].append(slot_data)

                                # 2) Si todavía hay lugares libres, agregar slot vacío
                                if cantidad_ocupados < capacidad:
                                    lugares_libres = capacidad - cantidad_ocupados
                                    horarios_por_consultorio[est_nombre].append({
                                        'hora_inicio': hora_actual,
                                        'hora_fin': hora_fin_slot,
                                        'turno': None,
                                        'disponible': True,
                                        'lugares_restantes': lugares_libres,
                                        'archivo_url': '',
                                    })
                        hora_actual = hora_fin_slot

        # Turnos fuera de slot (sobreturnos)
        turnos_en_slots = {s['turno'].id for slots in horarios_por_consultorio.values() for s in slots if s['turno']}
        turnos_fuera_de_slot = [t for t in turnos_dia if t.id not in turnos_en_slots]
        for turno in turnos_fuera_de_slot:
            est_nombre = turno.establecimiento.nombre if turno.establecimiento else 'Consultorio'
            if est_nombre not in horarios_por_consultorio:
                horarios_por_consultorio[est_nombre] = []
            puede_reactivar = False
            if turno.estado == 'no_asistio' and turno.no_asistio_automatico:
                ahora = datetime.now()
                fecha_hora_inicio = datetime.combine(turno.fecha, turno.hora_inicio)
                limite = fecha_hora_inicio + timedelta(minutes=60)
                puede_reactivar = ahora <= limite
            archivo_url = turno.archivo.url if turno.archivo else ''
            horarios_por_consultorio[est_nombre].append({
                'hora_inicio': turno.hora_inicio,
                'hora_fin': turno.hora_fin,
                'turno': turno,
                'disponible': False,
                'lugares_restantes': 0,
                'puede_reactivar': puede_reactivar,
                'mostrar_como_sobreturno': turno.estado not in ['no_asistio', 'completado', 'cancelado'],
                'archivo_url': archivo_url,
            })

        for est in horarios_por_consultorio:
            horarios_por_consultorio[est].sort(key=lambda x: x['hora_inicio'])

        dias_semana.append({
            'fecha': dia,
            'nombre': nombres_dias[i],
            'es_hoy': dia == hoy,
            'atiende': any(len(slots) > 0 for slots in horarios_por_consultorio.values()),
            'bloqueado': dia_bloqueado,
            'bloqueos': bloqueos_dia,
            'horarios_por_consultorio': horarios_por_consultorio,
        })

    semana_anterior = lunes - timedelta(days=7)
    semana_siguiente = lunes + timedelta(days=7)

    profesionales_consultorio = None
    if request.user.rol == 'secretaria':
        profesionales_consultorio = Profesional.objects.filter(
            establecimientos=request.user.establecimiento, activo=True, atiende_por_orden=False
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

from core_app.utils import get_establecimiento_activo

@login_required
def asignar_turno_calendario(request):
    if request.user.rol not in ['profesional', 'secretaria']:
        return redirect('home')

    if request.user.rol == 'secretaria':
        profesional_id = request.GET.get('profesional')
        if profesional_id:
            profesional = get_object_or_404(Profesional, id=profesional_id)
        else:
            profesional = Profesional.objects.filter(
                establecimientos=request.user.establecimiento, activo=True
            ).first()
        establecimiento_filtro = request.user.establecimiento
    else:
        profesional = get_object_or_404(Profesional, usuario=request.user)
        establecimiento_filtro = get_establecimiento_activo(request, profesional)

        if not establecimiento_filtro:
            if profesional.establecimientos.count() == 1:
                establecimiento_filtro = profesional.establecimientos.first()
            else:
                messages.error(request, 'Seleccioná tu consultorio activo.')
                return redirect('seleccionar_consultorio')

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

    # Agenda filtrada por consultorio activo
    agenda = Agenda.objects.filter(
        profesional=profesional,
        activo=True,
        fecha_inicio__lte=fecha,
        establecimiento=establecimiento_filtro
    ).filter(
        Q(fecha_fin__isnull=True) | Q(fecha_fin__gte=fecha)
    ).first()

    duracion = 30
    if agenda:
        horario_atencion = HorarioAtencion.objects.filter(
            agenda=agenda, dia=fecha.weekday()
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
            return redirect(request.path + f'?fecha={fecha_str}&hora={hora_str}')

        paciente = get_object_or_404(Paciente, id=paciente_id)

        # Validar que el establecimiento que llegue sea el activo
        establecimiento_id = request.POST.get('establecimiento')
        if establecimiento_id:
            establecimiento = get_object_or_404(Establecimiento, id=establecimiento_id)
            if establecimiento != establecimiento_filtro:
                messages.error(request, 'No podés asignar turnos en otro consultorio.')
                return redirect('calendario_semanal')
        else:
            establecimiento = establecimiento_filtro

        turnos_en_horario = TurnoProfesional.objects.filter(
            profesional=profesional,
            fecha=fecha,
            hora_inicio=hora,
            estado__in=['pendiente', 'confirmado'],
            establecimiento=establecimiento_filtro,
        ).count()

        max_simultaneos = agenda.pacientes_simultaneos if agenda else 1

        if turnos_en_horario >= max_simultaneos:
            messages.error(request, f'Horario completo (máx. {max_simultaneos} pacientes).')
            return redirect('calendario_semanal')

        turno = TurnoProfesional.objects.create(
            profesional=profesional,
            establecimiento=establecimiento,
            paciente=paciente,
            fecha=fecha,
            hora_inicio=hora,
            hora_fin=hora_fin,
            estado='pendiente',
            tipo_consulta=tipo_consulta,
            notas_internas=notas,
        )

        try:
            threading.Thread(target=crear_evento_google, args=(turno,)).start()
        except:
            pass

        messages.success(
            request,
            f'Turno asignado a {paciente.nombre_completo} el {fecha.strftime("%d/%m/%Y")} a las {hora_str}.'
        )
        return redirect('calendario_semanal')

    # GET: búsqueda de pacientes filtrada por consultorio
    busqueda = request.GET.get('buscar', '')
    pacientes = []
    if busqueda:
        pacientes = Paciente.objects.filter(
            Q(nombre__icontains=busqueda) |
            Q(apellido__icontains=busqueda) |
            Q(dni__icontains=busqueda)
        )

        if establecimiento_filtro:
            pacientes = pacientes.filter(
                turnoprofesional__establecimiento=establecimiento_filtro
            ).distinct()

        pacientes = pacientes[:15]

    return render(request, 'turnos_profesionales/asignar_calendario.html', {
        'profesional': profesional,
        'fecha': fecha,
        'hora': hora,
        'hora_fin': hora_fin,
        'fecha_str': fecha_str,
        'hora_str': hora_str,
        'pacientes': pacientes,
        'busqueda': busqueda,
        'establecimiento_activo': establecimiento_filtro,
    })


# ============ BLOQUEAR/DESBLOQUEAR ============

@login_required
def bloquear_dia(request):
    if request.user.rol not in ['profesional', 'secretaria']:
        return redirect('home')
    
    if request.user.rol == 'secretaria':
        profesional_id = request.GET.get('profesional')
        if profesional_id:
            profesional = get_object_or_404(Profesional, id=profesional_id)
        else:
            profesional = Profesional.objects.filter(
                establecimientos=request.user.establecimiento, activo=True
            ).first()
    else:
        profesional = get_object_or_404(Profesional, usuario=request.user)
    
    if not profesional:
        messages.error(request, 'No hay profesionales disponibles.')
        return redirect('home')
    
    if request.method == 'POST':
        fecha_str = request.POST.get('fecha')
        hora_inicio_str = request.POST.get('hora_inicio', '')
        hora_fin_str = request.POST.get('hora_fin', '')
        motivo = request.POST.get('motivo', '')
        dia_completo = request.POST.get('dia_completo') == 'on'
        confirmar = request.POST.get('confirmar_bloqueo') == 'si'  # <-- nuevo
        
        if not fecha_str:
            messages.error(request, 'Seleccioná una fecha.')
            return redirect('calendario_semanal')
        
        try:
            fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        except ValueError:
            messages.error(request, 'Fecha inválida.')
            return redirect('calendario_semanal')
        
        # Obtener la agenda activa para esa fecha
        agenda = Agenda.objects.filter(
            profesional=profesional, activo=True,
            fecha_inicio__lte=fecha
        ).filter(
            Q(fecha_fin__isnull=True) | Q(fecha_fin__gte=fecha)
        ).first()
        
        if not agenda:
            messages.error(request, 'No tenés agenda configurada para esa fecha.')
            return redirect('calendario_semanal')
        
        # Determinar rango horario
        if dia_completo:
            hora_inicio = None
            hora_fin = None
        else:
            if not hora_inicio_str or not hora_fin_str:
                messages.error(request, 'Indicá horario de inicio y fin.')
                return redirect('calendario_semanal')
            try:
                hora_inicio = datetime.strptime(hora_inicio_str, '%H:%M').time()
                hora_fin = datetime.strptime(hora_fin_str, '%H:%M').time()
            except ValueError:
                messages.error(request, 'Horario inválido.')
                return redirect('calendario_semanal')
        
        # 🔍 Buscar turnos que se solapen con el bloqueo
        conflictos = TurnoProfesional.objects.filter(
            profesional=profesional,
            establecimiento=agenda.establecimiento,
            fecha=fecha,
            estado__in=['pendiente', 'confirmado']
        )
        if dia_completo:
            # Todos los turnos de ese día
            conflictos = conflictos.filter(fecha=fecha)
        else:
            # Turnos cuyo horario se superpone con el bloqueo
            conflictos = conflictos.filter(
                hora_inicio__lt=hora_fin,
                hora_fin__gt=hora_inicio
            )
        
        # Si hay conflictos y no se confirmó la cancelación
        if conflictos.exists() and not confirmar:
            # Mostrar página de confirmación con los turnos afectados
            return render(request, 'turnos_profesionales/bloquear_confirmacion.html', {
                'conflictos': conflictos,
                'fecha': fecha,
                'hora_inicio': hora_inicio_str,
                'hora_fin': hora_fin_str,
                'motivo': motivo,
                'dia_completo': dia_completo,
                'agenda': agenda,
            })
        
        import threading
        from django.core.mail import send_mail
        from django.conf import settings

        if conflictos.exists():
            for turno in conflictos:
                turno.estado = 'cancelado'
                turno.notas_internas = (turno.notas_internas or '') + f'\nCancelado por bloqueo: {motivo}'
                turno.save()

                from .notificaciones import notificar_cancelacion_turno
                # En el loop:
                notificar_cancelacion_turno(turno, cancelado_por='sistema', motivo=motivo)

                # Enviar notificación por email al paciente (si tiene email)
                # if turno.paciente.email:
                #     subject = f'Turno cancelado - {turno.establecimiento.nombre}'
                #     message = (
                #         f'Hola {turno.paciente.nombre_completo},\n\n'
                #         f'Tu turno del día {turno.fecha.strftime("%d/%m/%Y")} '
                #         f'a las {turno.hora_inicio.strftime("%H:%M")} con '
                #         f'{turno.profesional.nombre_completo} fue cancelado.\n'
                #         f'Motivo: {motivo}\n\n'
                #         f'Podés ingresar a tu panel para reprogramar:\n'
                #         f'http://127.0.0.1:8000/usuarios/login/\n\n'
                #         f'Saludos.'
                #     )
                    # try:
                        # Envío asíncrono para no demorar la respuesta
                    #     threading.Thread(
                    #         target=send_mail,
                    #         args=(subject, message, settings.DEFAULT_FROM_EMAIL, [turno.paciente.email]),
                    #         kwargs={'fail_silently': True}
                    #     ).start()
                    # except Exception:
                    #     pass 

            messages.warning(request, f'Se cancelaron {conflictos.count()} turno(s) afectado(s).')
        
        # Crear el bloqueo
        BloqueoAgenda.objects.create(
            agenda=agenda,
            fecha=fecha,
            hora_inicio=hora_inicio,
            hora_fin=hora_fin,
            motivo=motivo if motivo else 'Día no laborable'
        )
        
        messages.success(request, f'Bloqueo aplicado el {fecha.strftime("%d/%m/%Y")}.')
        return redirect('calendario_semanal')
    
    return redirect('calendario_semanal')

@login_required
def desbloquear_dia(request, bloqueo_id):
    if request.user.rol not in ['profesional', 'secretaria']:
        return redirect('home')
    
    bloqueo = get_object_or_404(BloqueoAgenda, id=bloqueo_id)
    
    if request.user.rol == 'secretaria':
        if request.user.establecimiento not in bloqueo.agenda.profesional.establecimientos.all():
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
    if request.user.rol != 'secretaria':
        messages.error(request, 'No tenés acceso.')
        return redirect('home')
    
    if not request.user.establecimiento:
        messages.error(request, 'No tenés un consultorio asignado.')
        return redirect('home')
    
    establecimiento = request.user.establecimiento
    hoy = date.today()
    
    profesionales = Profesional.objects.filter(establecimientos=establecimiento, activo=True)
    
    profesional_id = request.GET.get('profesional')
    profesional_seleccionado = None
    if profesional_id:
        profesional_seleccionado = get_object_or_404(Profesional, id=profesional_id, establecimientos=establecimiento)
    
    marcar_turnos_vencidos()
    
    if profesional_seleccionado:
        turnos_hoy_qs = TurnoProfesional.objects.filter(
            profesional=profesional_seleccionado, fecha=hoy
        ).order_by('hora_inicio')
    else:
        turnos_hoy_qs = TurnoProfesional.objects.filter(
            profesional__in=profesionales, establecimiento=establecimiento, fecha=hoy
        ).order_by('profesional', 'hora_inicio')
    
    # Lista para el template con el atributo puede_reactivar
    turnos_hoy = list(turnos_hoy_qs)
    ahora = datetime.now()
    for turno in turnos_hoy:
        if turno.estado == 'no_asistio' and turno.no_asistio_automatico:
            fecha_hora_inicio = datetime.combine(turno.fecha, turno.hora_inicio)
            limite = fecha_hora_inicio + timedelta(minutes=60)
            turno.puede_reactivar = (ahora <= limite)
        else:
            turno.puede_reactivar = False
    
    # Estadísticas con el queryset original
    total_hoy = turnos_hoy_qs.count()
    pendientes = turnos_hoy_qs.filter(estado='pendiente').count()
    confirmados = turnos_hoy_qs.filter(estado='confirmado').count()
    en_sala = turnos_hoy_qs.filter(estado='en_sala').count()
    
    profesionales_orden_llegada = Profesional.objects.filter(
        establecimientos=establecimiento,
        activo=True,
        atiende_por_orden=True
    )
    
    sesiones_por_turno = {}
    for turno in turnos_hoy_qs:
        os_paciente = turno.paciente.mis_obras_sociales.filter(
            profesional=turno.profesional,
            activa=True
        ).first()
        sesiones_por_turno[turno.id] = os_paciente

    # Próximos turnos (para la nueva sección)
    manana = hoy + timedelta(days=1)
    if profesional_seleccionado:
        proximos_turnos_qs = TurnoProfesional.objects.filter(
            profesional=profesional_seleccionado,
            establecimiento=establecimiento,
            fecha__gte=manana,
            estado__in=['pendiente', 'confirmado']
        ).order_by('fecha', 'hora_inicio')[:10]
    else:
        proximos_turnos_qs = TurnoProfesional.objects.filter(
            profesional__in=profesionales,
            establecimiento=establecimiento,
            fecha__gte=manana,
            estado__in=['pendiente', 'confirmado']
        ).order_by('fecha', 'hora_inicio')[:10]

    hay_mas_proximos = proximos_turnos_qs.count() == 10  # Simplifico: si trajo 10, probablemente haya más
    
    return render(request, 'turnos_profesionales/panel_secretaria.html', {
        'profesionales': profesionales,
        'profesional_seleccionado': profesional_seleccionado,
        'profesionales_orden_llegada': profesionales_orden_llegada,
        'turnos_hoy': turnos_hoy,
        'proximos_turnos': proximos_turnos_qs,
        'hay_mas_proximos': hay_mas_proximos,
        'hoy': hoy,
        'total_hoy': total_hoy,
        'sesiones_por_turno': sesiones_por_turno,
        'pendientes': pendientes,
        'confirmados': confirmados,
        'en_sala': en_sala,
        'establecimiento': establecimiento,
    })

# ============ CALENDARIO MULTI ============

@login_required
def calendario_multi(request):
    if request.user.rol != 'secretaria':
        messages.error(request, 'Solo la secretaria puede ver este calendario.')
        return redirect('home')
    
    if not request.user.establecimiento:
        messages.error(request, 'No tenés un consultorio asignado.')
        return redirect('home')
    
    establecimiento = request.user.establecimiento
    profesionales = Profesional.objects.filter(establecimientos=establecimiento, activo=True).order_by('apellido', 'nombre')
    
    fecha_str = request.GET.get('fecha')
    if fecha_str:
        try:
            fecha_base = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        except ValueError:
            fecha_base = date.today()
    else:
        fecha_base = date.today()
    
    hoy = date.today()
    lunes = fecha_base - timedelta(days=fecha_base.weekday())
    nombres_dias = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
    dias_semana = []
    
    for i in range(7):
        dia = lunes + timedelta(days=i)
        turnos_por_profesional = {}
        for prof in profesionales:
            turnos_dia = TurnoProfesional.objects.filter(profesional=prof, fecha=dia).order_by('hora_inicio')
            turnos_por_profesional[prof.id] = {
                'profesional': prof, 'turnos': turnos_dia, 'atiende': False, 'color': prof.color_calendario
            }
            agenda = Agenda.objects.filter(profesional=prof, activo=True, fecha_inicio__lte=dia).filter(
                Q(fecha_fin__isnull=True) | Q(fecha_fin__gte=dia)
            ).first()
            if agenda:
                horario = HorarioAtencion.objects.filter(agenda=agenda, dia=dia.weekday()).first()
                if horario:
                    turnos_por_profesional[prof.id]['atiende'] = True
        dias_semana.append({
            'fecha': dia, 'nombre': nombres_dias[i], 'es_hoy': dia == hoy,
            'turnos_por_profesional': turnos_por_profesional,
        })
    
    semana_anterior = lunes - timedelta(days=7)
    semana_siguiente = lunes + timedelta(days=7)
    horas = ['08:00', '09:00', '10:00', '11:00', '12:00', '13:00', '14:00', '15:00', '16:00', '17:00', '18:00', '19:00']
    
    return render(request, 'turnos_profesionales/calendario_multi.html', {
        'profesionales': profesionales, 'dias_semana': dias_semana,
        'lunes': lunes, 'domingo': lunes + timedelta(days=6),
        'semana_anterior': semana_anterior.strftime('%Y-%m-%d'),
        'semana_siguiente': semana_siguiente.strftime('%Y-%m-%d'),
        'hoy': hoy, 'establecimiento': establecimiento, 'horas': horas,
    })


# ============ REPROGRAMAR TURNO ============
@login_required
def reprogramar_turno(request, turno_id):
    if request.user.rol not in ['profesional', 'secretaria']:
        return redirect('home')
    
    turno = get_object_or_404(TurnoProfesional, id=turno_id)
    
    if request.user.rol == 'secretaria':
        profesional = turno.profesional
        establecimiento_filtro = request.user.establecimiento
    else:
        profesional = get_object_or_404(Profesional, usuario=request.user)
        if request.user != turno.profesional.usuario:
            messages.error(request, 'No tenés permiso.')
            return redirect('panel_profesional')
        establecimiento_filtro = _get_establecimiento_activo(request, profesional)
    
    hoy = date.today()
    
    if request.method == 'POST':
        fecha_str = request.POST.get('fecha')
        hora_str = request.POST.get('hora')
        establecimiento_id = request.POST.get('establecimiento')
        
        if not all([fecha_str, hora_str]):
            messages.error(request, 'Seleccioná fecha y hora.')
            return redirect('reprogramar_turno', turno_id=turno.id)
        
        try:
            nueva_fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
            nueva_hora = datetime.strptime(hora_str, '%H:%M').time()
        except ValueError:
            messages.error(request, 'Fecha u hora inválida.')
            return redirect('reprogramar_turno', turno_id=turno.id)
        
        turno_original = TurnoProfesional.objects.get(pk=turno.pk)

        if nueva_fecha < hoy:
            messages.error(request, 'No podés reprogramar a una fecha pasada.')
            return redirect('reprogramar_turno', turno_id=turno.id)
        
        existe = TurnoProfesional.objects.filter(
            profesional=profesional, fecha=nueva_fecha, hora_inicio=nueva_hora,
            estado__in=['pendiente', 'confirmado']
        ).exclude(id=turno.id)
        if establecimiento_filtro:
            existe = existe.filter(establecimiento=establecimiento_filtro)
        if existe.exists():
            messages.error(request, 'Ese horario ya está ocupado.')
            return redirect('reprogramar_turno', turno_id=turno.id)
        
        if establecimiento_id:
            turno.establecimiento = get_object_or_404(Establecimiento, id=establecimiento_id)
        else:
            # Mantiene el establecimiento actual o usa el primero
            if not turno.establecimiento:
                turno.establecimiento = establecimiento_filtro if establecimiento_filtro else profesional.establecimientos.first()
        
        fecha_anterior = turno.fecha
        hora_anterior = turno.hora_inicio
        
        turno.fecha = nueva_fecha
        turno.hora_inicio = nueva_hora
        
        duracion = 30
        agenda = Agenda.objects.filter(profesional=profesional, activo=True, fecha_inicio__lte=nueva_fecha)
        if establecimiento_filtro:
            agenda = agenda.filter(establecimiento=establecimiento_filtro)
        agenda = agenda.filter(Q(fecha_fin__isnull=True) | Q(fecha_fin__gte=nueva_fecha)).first()
        if agenda:
            horario_atencion = HorarioAtencion.objects.filter(agenda=agenda, dia=nueva_fecha.weekday()).first()
            if horario_atencion:
                duracion = horario_atencion.duracion_turno
        
        turno.hora_fin = (datetime.combine(nueva_fecha, nueva_hora) + timedelta(minutes=duracion)).time()
        turno.save()

        from .notificaciones import notificar_reprogramacion_turno
        notificar_reprogramacion_turno(turno_original, turno)
        
        try:
            threading.Thread(target=eliminar_evento_google, args=(turno,)).start()
            threading.Thread(target=crear_evento_google, args=(turno,)).start()
        except:
            pass
        
        messages.success(request, f'Turno reprogramado del {fecha_anterior.strftime("%d/%m/%Y")} {hora_anterior.strftime("%H:%M")} → {nueva_fecha.strftime("%d/%m/%Y")} {nueva_hora.strftime("%H:%M")}.')
        if request.user.rol == 'secretaria':
            return redirect('panel_secretaria')
        return redirect('panel_profesional')
    
    # GET
    dias_disponibles = []
    agenda = Agenda.objects.filter(profesional=profesional, activo=True, fecha_inicio__lte=hoy + timedelta(days=30))
    if establecimiento_filtro:
        agenda = agenda.filter(establecimiento=establecimiento_filtro)
    agenda = agenda.first()
    if agenda:
        for i in range(30):
            fecha = hoy + timedelta(days=i)
            horario = HorarioAtencion.objects.filter(agenda=agenda, dia=fecha.weekday()).first()
            if horario:
                hora_actual = horario.hora_inicio
                slots = []
                while hora_actual < horario.hora_fin:
                    hora_fin_slot = (datetime.combine(fecha, hora_actual) + timedelta(minutes=horario.duracion_turno)).time()
                    if hora_fin_slot <= horario.hora_fin:
                        ocupado = TurnoProfesional.objects.filter(
                            profesional=profesional, fecha=fecha, hora_inicio=hora_actual,
                            estado__in=['pendiente', 'confirmado']
                        ).exclude(id=turno.id)
                        if establecimiento_filtro:
                            ocupado = ocupado.filter(establecimiento=establecimiento_filtro)
                        if not ocupado.exists():
                            slots.append({'hora': hora_actual.strftime('%H:%M'), 'hora_fin': hora_fin_slot.strftime('%H:%M')})
                    hora_actual = hora_fin_slot
                if slots:
                    dias_disponibles.append({
                        'fecha': fecha, 'fecha_str': fecha.strftime('%Y-%m-%d'),
                        'nombre_dia': fecha.strftime('%A'), 'es_hoy': fecha == hoy, 'slots': slots
                    })
    
    return render(request, 'turnos_profesionales/reprogramar_turno.html', {
        'profesional': profesional, 'turno': turno, 'dias_disponibles': dias_disponibles, 'hoy': hoy
    })


# ============ SOBRETURNOS ============
@login_required
def crear_sobreturno(request, paciente_id):
    if request.user.rol not in ['profesional', 'secretaria']:
        return redirect('home')
    
    if request.user.rol == 'secretaria':
        profesional_id = request.GET.get('profesional')
        if profesional_id:
            profesional = get_object_or_404(Profesional, id=profesional_id)
        else:
            profesional = Profesional.objects.filter(
                establecimientos=request.user.establecimiento, activo=True
            ).first()
        establecimiento_filtro = request.user.establecimiento
    else:
        profesional = get_object_or_404(Profesional, usuario=request.user)
        establecimiento_filtro = _get_establecimiento_activo(request, profesional)
    
    paciente = get_object_or_404(Paciente, id=paciente_id)
    hoy = date.today()
    
    if request.method == 'POST':
        fecha_str = request.POST.get('fecha')
        hora_str = request.POST.get('hora')
        duracion = int(request.POST.get('duracion', 15))
        tipo_consulta = request.POST.get('tipo_consulta', 'URGENCIA - Sobreturno')
        notas = request.POST.get('notas', '')
        establecimiento_id = request.POST.get('establecimiento')
        
        if not all([fecha_str, hora_str]):
            messages.error(request, 'Seleccioná fecha y hora.')
            return redirect('crear_sobreturno', paciente_id=paciente.id)
        
        try:
            fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
            hora = datetime.strptime(hora_str, '%H:%M').time()
        except ValueError:
            messages.error(request, 'Fecha u hora inválida.')
            return redirect('crear_sobreturno', paciente_id=paciente.id)
        
        hora_fin = (datetime.combine(fecha, hora) + timedelta(minutes=duracion)).time()
        
        establecimiento = None
        if establecimiento_id:
            establecimiento = get_object_or_404(Establecimiento, id=establecimiento_id)
        else:
            establecimiento = establecimiento_filtro if establecimiento_filtro else profesional.establecimientos.first()
        
        turno = TurnoProfesional.objects.create(
            profesional=profesional, establecimiento=establecimiento,
            paciente=paciente, fecha=fecha, hora_inicio=hora,
            hora_fin=hora_fin, estado='confirmado',
            tipo_consulta=tipo_consulta, notas_internas=notas, es_sobreturno=True
        )
        
        try:
            threading.Thread(target=crear_evento_google, args=(turno,)).start()
        except:
            pass
        
        messages.success(request, f'¡Sobreturno creado! {paciente.nombre_completo} - {fecha.strftime("%d/%m/%Y")} a las {hora_str}.')
        if request.user.rol == 'secretaria':
            return redirect('panel_secretaria')
        return redirect('panel_profesional')
    
    return render(request, 'turnos_profesionales/sobreturno.html', {
        'profesional': profesional, 'paciente': paciente, 'hoy': hoy
    })

from core_app.utils import get_establecimiento_activo

@login_required
def sobreturno_calendario(request):
    if request.user.rol not in ['profesional', 'secretaria']:
        return redirect('home')

    if request.user.rol == 'secretaria':
        profesional_id = request.GET.get('profesional')
        if profesional_id:
            profesional = get_object_or_404(Profesional, id=profesional_id)
        else:
            profesional = Profesional.objects.filter(
                establecimientos=request.user.establecimiento, activo=True
            ).first()
        establecimiento_filtro = request.user.establecimiento
    else:
        profesional = get_object_or_404(Profesional, usuario=request.user)
        establecimiento_filtro = get_establecimiento_activo(request, profesional)

        # Si no hay consultorio activo y tiene más de uno, forzar selección
        if not establecimiento_filtro:
            if profesional.establecimientos.count() == 1:
                establecimiento_filtro = profesional.establecimientos.first()
            else:
                messages.error(request, 'Seleccioná tu consultorio activo.')
                return redirect('seleccionar_consultorio')

    fecha_str = request.GET.get('fecha', '')
    hora_str = request.GET.get('hora', '')
    hora_fin_str = request.GET.get('hora_fin', '')

    if request.method == 'POST':
        paciente_id = request.POST.get('paciente_id')
        tipo_consulta = request.POST.get('tipo_consulta', 'URGENCIA - Sobreturno')
        notas = request.POST.get('notas', '')
        establecimiento_id = request.POST.get('establecimiento')

        if not paciente_id:
            messages.error(request, 'Seleccioná un paciente.')
            return redirect(request.path + f'?fecha={fecha_str}&hora={hora_str}&hora_fin={hora_fin_str}')

        paciente = get_object_or_404(Paciente, id=paciente_id)

        # Validar que el establecimiento enviado sea el activo
        if establecimiento_id:
            establecimiento = get_object_or_404(Establecimiento, id=establecimiento_id)
            if establecimiento != establecimiento_filtro:
                messages.error(request, 'No podés crear sobreturnos en otro consultorio.')
                return redirect('calendario_semanal')
        else:
            establecimiento = establecimiento_filtro

        try:
            fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
            hora = datetime.strptime(hora_str, '%H:%M').time()
            if hora_fin_str:
                hora_fin = datetime.strptime(hora_fin_str, '%H:%M').time()
            else:
                hora_fin = (datetime.combine(fecha, hora) + timedelta(minutes=15)).time()
        except ValueError:
            messages.error(request, 'Fecha u hora inválida.')
            return redirect('calendario_semanal')

        turno = TurnoProfesional.objects.create(
            profesional=profesional,
            establecimiento=establecimiento,
            paciente=paciente,
            fecha=fecha,
            hora_inicio=hora,
            hora_fin=hora_fin,
            estado='confirmado',
            tipo_consulta=tipo_consulta,
            notas_internas=notas,
            es_sobreturno=True,
        )

        try:
            threading.Thread(target=crear_evento_google, args=(turno,)).start()
        except:
            pass

        messages.success(request, f'🚨 Sobreturno creado para {paciente.nombre_completo}.')
        return redirect('calendario_semanal')

    # GET: búsqueda de pacientes filtrada por el consultorio activo
    busqueda = request.GET.get('buscar', '')
    pacientes = []
    if busqueda:
        pacientes = Paciente.objects.filter(
            Q(nombre__icontains=busqueda) |
            Q(apellido__icontains=busqueda) |
            Q(dni__icontains=busqueda)
        )

        if establecimiento_filtro:
            pacientes = pacientes.filter(
                turnoprofesional__establecimiento=establecimiento_filtro
            ).distinct()

        pacientes = pacientes[:15]

    return render(request, 'turnos_profesionales/sobreturno_calendario.html', {
        'profesional': profesional,
        'fecha_str': fecha_str,
        'hora_str': hora_str,
        'hora_fin_str': hora_fin_str,
        'pacientes': pacientes,
        'busqueda': busqueda,
        'establecimiento_activo': establecimiento_filtro,
    })

# ============ RECETA PDF ============
from reportlab.lib.pagesizes import A5
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas

@login_required
def generar_receta(request, evolucion_id):
    evolucion = get_object_or_404(Evolucion, id=evolucion_id)
    paciente = evolucion.historia_clinica.paciente
    profesional = evolucion.profesional

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="indicacion_{paciente.apellido}_{evolucion.creado.strftime("%Y%m%d")}.pdf"'

    p = canvas.Canvas(response, pagesize=A5)
    width, height = A5

    # Márgenes
    margen_izq = 1.5*cm
    margen_der = width - 1.5*cm
    y = height - 1.5*cm

    # ─── RECUADRO EXTERNO ────────────────────────
    p.setStrokeColorRGB(0.2, 0.2, 0.2)
    p.setLineWidth(1.5)
    p.rect(1*cm, 1*cm, width - 2*cm, height - 2*cm, stroke=1, fill=0)

    # ─── TÍTULO ──────────────────────────────────
    p.setFont("Helvetica-Bold", 14)
    p.drawCentredString(width/2, y, "INDICACIÓN MÉDICA")
    y -= 0.8*cm
    p.setFont("Helvetica", 8)
    p.drawCentredString(width/2, y, "(No válida para farmacia – Uso exclusivo del paciente)")
    y -= 0.4*cm
    p.setFont("Helvetica-Oblique", 7)
    p.drawCentredString(width/2, y, "Documento informativo – No reemplaza una receta oficial")
    y -= 0.6*cm
    # Línea separadora
    p.line(margen_izq, y, margen_der, y)
    y -= 0.8*cm

    # ─── DATOS DEL PROFESIONAL ──────────────────
    p.setFont("Helvetica-Bold", 11)
    p.drawString(margen_izq, y, f"Dr/a. {profesional.nombre_completo}")
    y -= 0.5*cm
    p.setFont("Helvetica", 9)
    p.drawString(margen_izq, y, f"{profesional.get_especialidad_display()}  ·  M.N. {profesional.matricula}")
    y -= 0.5*cm
    if profesional.establecimientos.first():
        est = profesional.establecimientos.first()
        p.drawString(margen_izq, y, f"{est.nombre}  ·  {est.direccion}  ·  Tel: {est.telefono}")
    y -= 0.8*cm
    p.line(margen_izq, y, margen_der, y)
    y -= 0.8*cm

    # ─── DATOS DEL PACIENTE ─────────────────────
    p.setFont("Helvetica-Bold", 9)
    p.drawString(margen_izq, y, "Paciente:")
    p.setFont("Helvetica", 9)
    p.drawString(margen_izq + 3*cm, y, paciente.nombre_completo)
    y -= 0.5*cm
    p.drawString(margen_izq, y, f"DNI: {paciente.dni}")
    p.drawString(margen_izq + 5*cm, y, f"Fecha: {evolucion.creado.strftime('%d/%m/%Y')}")
    y -= 0.5*cm
    if paciente.obra_social:
        p.drawString(margen_izq, y, f"O.S.: {paciente.obra_social.nombre}  ·  N° {paciente.numero_afiliado or '—'}")
    y -= 0.8*cm
    p.line(margen_izq, y, margen_der, y)
    y -= 0.8*cm

    # ─── DIAGNÓSTICO (si existe) ────────────────
    if evolucion.diagnostico:
        p.setFont("Helvetica-Bold", 9)
        p.drawString(margen_izq, y, "Diagnóstico:")
        y -= 0.5*cm
        p.setFont("Helvetica", 9)
        for linea in evolucion.diagnostico.split('\n')[:3]:  # limitar a 3 líneas
            p.drawString(margen_izq + 0.5*cm, y, linea.strip()[:80])
            y -= 0.4*cm
        y -= 0.6*cm

    # ─── MEDICACIÓN (Rp.) ────────────────────────
    p.setFont("Helvetica-Bold", 12)
    p.drawString(margen_izq, y, "Rp.")
    y -= 0.7*cm
    p.setFont("Helvetica", 10)
    medicacion = evolucion.medicacion_recetada or "No se recetó medicación"
    for linea in medicacion.split('\n')[:5]:
        p.drawString(margen_izq + 0.5*cm, y, linea.strip()[:80])
        y -= 0.5*cm
    y -= 0.5*cm

    # ─── INDICACIONES ───────────────────────────
    if evolucion.indicaciones:
        p.setFont("Helvetica-Bold", 9)
        p.drawString(margen_izq, y, "Indicaciones:")
        y -= 0.5*cm
        p.setFont("Helvetica", 9)
        for linea in evolucion.indicaciones.split('\n')[:6]:
            p.drawString(margen_izq + 0.5*cm, y, linea.strip()[:80])
            y -= 0.4*cm
        y -= 0.6*cm

    # ─── FIRMA DEL PROFESIONAL ──────────────────
    # Línea para firma
    firma_y = y - 0.2*cm
    p.line(margen_izq, firma_y, margen_izq + 6*cm, firma_y)
    p.setFont("Helvetica-Bold", 9)
    p.drawString(margen_izq, firma_y - 0.5*cm, f"Dr/a. {profesional.nombre_completo}")
    p.setFont("Helvetica", 8)
    p.drawString(margen_izq, firma_y - 1.0*cm, f"M.N. {profesional.matricula}")
    p.drawString(margen_izq, firma_y - 1.4*cm, profesional.get_especialidad_display())

    # ─── SELLO DEL PROFESIONAL ──────────────────
    sello_x = margen_izq + 8*cm
    sello_y = firma_y - 2.5*cm
    p.setStrokeColorRGB(0.8, 0.2, 0.2)
    p.setLineWidth(1)
    p.rect(sello_x, sello_y, 3.2*cm, 2.8*cm, stroke=1, fill=0)
    p.setFont("Helvetica", 6)
    p.drawCentredString(sello_x + 1.6*cm, sello_y + 1.8*cm, "FIRMA Y SELLO")
    p.drawCentredString(sello_x + 1.6*cm, sello_y + 1.2*cm, "DEL PROFESIONAL")

    # ─── PIE DE PÁGINA LEGAL ────────────────────
    # p.setFont("Helvetica", 6)
    # p.setFillColorRGB(0.5, 0.5, 0.5)
    # p.drawCentredString(width/2, 1.8*cm, "Receta válida por 30 días desde la fecha de emisión.")

    p.showPage()
    p.save()
    return response

# ============ DASHBOARD ============
@login_required
def dashboard(request):
    if request.user.rol not in ['profesional', 'secretaria']:
        messages.error(request, 'No tenés acceso.')
        return redirect('home')
    
    if request.user.rol == 'secretaria':
        establecimiento = request.user.establecimiento
        profesionales = Profesional.objects.filter(establecimientos=establecimiento, activo=True)
        profesional_seleccionado = None
        profesional_id = request.GET.get('profesional')
        if profesional_id:
            profesional_seleccionado = get_object_or_404(Profesional, id=profesional_id, establecimientos=establecimiento)
            turnos_base = TurnoProfesional.objects.filter(profesional=profesional_seleccionado, establecimiento=establecimiento)
        else:
            turnos_base = TurnoProfesional.objects.filter(profesional__in=profesionales, establecimiento=establecimiento)
        establecimiento_filtro = establecimiento
    else:
        profesional = get_object_or_404(Profesional, usuario=request.user)
        establecimiento_filtro = _get_establecimiento_activo(request, profesional)
        turnos_base = TurnoProfesional.objects.filter(profesional=profesional)
        if establecimiento_filtro:
            turnos_base = turnos_base.filter(establecimiento=establecimiento_filtro)
        profesional_seleccionado = profesional
        profesionales = None
        establecimiento = None
    
    hoy = date.today()
    periodo = request.GET.get('periodo', 'mes')
    mes = request.GET.get('mes')
    anio = request.GET.get('anio')
    
    # ... (cálculo de inicio y fin según periodo, igual que antes)
    if periodo == 'hoy':
        inicio = hoy
        fin = hoy
    elif periodo == 'semana':
        inicio = hoy - timedelta(days=hoy.weekday())
        fin = inicio + timedelta(days=6)
    elif periodo == 'mes':
        if mes and anio:
            try:
                mes_int = int(mes)
                anio_int = int(anio)
                inicio = date(anio_int, mes_int, 1)
                if mes_int == 12:
                    fin = date(anio_int, 12, 31)
                else:
                    fin = date(anio_int, mes_int + 1, 1) - timedelta(days=1)
            except (ValueError, TypeError):
                inicio = hoy.replace(day=1)
                fin = (inicio + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        else:
            inicio = hoy.replace(day=1)
            fin = (inicio + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    elif periodo == 'año':
        if anio:
            try:
                anio_int = int(anio)
                inicio = date(anio_int, 1, 1)
                fin = date(anio_int, 12, 31)
            except (ValueError, TypeError):
                inicio = hoy.replace(month=1, day=1)
                fin = hoy.replace(month=12, day=31)
        else:
            inicio = hoy.replace(month=1, day=1)
            fin = hoy.replace(month=12, day=31)
    else:
        inicio = hoy.replace(day=1)
        fin = (inicio + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    
    turnos_periodo = turnos_base.filter(fecha__range=[inicio, fin])
    
    total_turnos = turnos_periodo.count()
    completados = turnos_periodo.filter(estado='completado').count()
    cancelados = turnos_periodo.filter(estado='cancelado').count()
    no_asistieron = turnos_periodo.filter(estado='no_asistio').count()
    pendientes = turnos_periodo.filter(estado='pendiente').count()
    tasa_asistencia = round((completados / total_turnos) * 100) if total_turnos > 0 else 0
    pacientes_unicos = turnos_periodo.values('paciente').distinct().count()
    obras_sociales = turnos_periodo.exclude(paciente__obra_social__isnull=True).values(
        'paciente__obra_social__nombre', 'paciente__obra_social__sigla'
    ).annotate(total=Count('id')).order_by('-total')[:5]
    pacientes_frecuentes = turnos_periodo.values(
        'paciente__nombre', 'paciente__apellido', 'paciente__id'
    ).annotate(total=Count('id')).order_by('-total')[:10]
    turnos_por_dia = turnos_periodo.values('fecha').annotate(total=Count('id')).order_by('fecha')
    turnos_por_estado = [
        {'estado': 'Completados', 'total': completados, 'color': '#28a745'},
        {'estado': 'Cancelados', 'total': cancelados, 'color': '#dc3545'},
        {'estado': 'No Asistieron', 'total': no_asistieron, 'color': '#6c757d'},
        {'estado': 'Pendientes', 'total': pendientes, 'color': '#ffc107'},
    ]
    total_coseguros = turnos_periodo.filter(monto_coseguro__isnull=False).aggregate(total=Sum('monto_coseguro'))['total'] or 0
    total_os = turnos_periodo.filter(monto_os__isnull=False).aggregate(total=Sum('monto_os'))['total'] or 0
    total_facturado = total_coseguros + total_os

    # Total de pagos particulares (sin OS)
    total_particulares = turnos_periodo.filter(
        Q(monto_os__isnull=True) | Q(monto_os=0),
        estado='completado',
        monto_total__isnull=False
    ).aggregate(total=Sum('monto_total'))['total'] or 0

    # Facturado total real (OS + coseguros + particulares)
    total_facturado = total_os + total_coseguros + total_particulares
    
    comparativa_profesional = []
    if request.user.rol == 'secretaria' and not profesional_seleccionado:
        comparativa_profesional = turnos_periodo.values('profesional__nombre', 'profesional__apellido').annotate(
            total=Count('id'), completados=Count('id', filter=Q(estado='completado')),
            cancelados=Count('id', filter=Q(estado='cancelado'))
        ).order_by('-total')
    
    return render(request, 'turnos_profesionales/dashboard.html', {
        'total_turnos': total_turnos, 'completados': completados,
        'cancelados': cancelados, 'no_asistieron': no_asistieron,
        'pendientes': pendientes, 'tasa_asistencia': tasa_asistencia,
        'pacientes_unicos': pacientes_unicos, 'obras_sociales': obras_sociales,
        'pacientes_frecuentes': pacientes_frecuentes, 'turnos_por_dia': turnos_por_dia,
        'turnos_por_estado': turnos_por_estado, 'total_coseguros': total_coseguros,
        'comparativa_profesional': comparativa_profesional, 'periodo': periodo,
        'inicio': inicio, 'fin': fin, 'profesionales': profesionales,
        'profesional_seleccionado': profesional_seleccionado,
        'total_os': total_os,
        'total_facturado': total_facturado,
        'mes_actual': inicio.month,
        'anio_actual': inicio.year,
        'total_particulares': total_particulares,
    })


# ============ EXPORTAR EXCEL ============
@login_required
def exportar_excel(request):
    if request.user.rol not in ['profesional', 'secretaria']:
        return redirect('home')
    
    hoy = date.today()
    
    if request.user.rol == 'secretaria':
        establecimiento = request.user.establecimiento
        profesionales = Profesional.objects.filter(establecimientos=establecimiento, activo=True)
        profesional_id = request.GET.get('profesional')
        if profesional_id:
            profesional_seleccionado = get_object_or_404(Profesional, id=profesional_id, establecimientos=establecimiento)
            turnos_base = TurnoProfesional.objects.filter(profesional=profesional_seleccionado, establecimiento=establecimiento)
        else:
            turnos_base = TurnoProfesional.objects.filter(profesional__in=profesionales, establecimiento=establecimiento)
        establecimiento_filtro = establecimiento
    else:
        profesional = get_object_or_404(Profesional, usuario=request.user)
        establecimiento_filtro = _get_establecimiento_activo(request, profesional)
        turnos_base = TurnoProfesional.objects.filter(profesional=profesional)
        if establecimiento_filtro:
            turnos_base = turnos_base.filter(establecimiento=establecimiento_filtro)
    
    periodo = request.GET.get('periodo', 'mes')
    if periodo == 'hoy':
        inicio = hoy
        fin = hoy
    elif periodo == 'semana':
        inicio = hoy - timedelta(days=hoy.weekday())
        fin = inicio + timedelta(days=6)
    elif periodo == 'mes':
        inicio = hoy.replace(day=1)
        fin = (inicio + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    else:
        inicio = hoy.replace(month=1, day=1)
        fin = hoy.replace(month=12, day=31)
    
    turnos_periodo = turnos_base.filter(fecha__range=[inicio, fin])
    
    wb = Workbook()
    ws = wb.active
    ws.title = "Turnos"
    ws.append(['Fecha', 'Hora', 'Paciente', 'DNI', 'Obra Social', 'Estado', 'Coseguro', 'Consultorio'])
    
    for t in turnos_periodo:
        ws.append([
            t.fecha.strftime('%d/%m/%Y'), t.hora_inicio.strftime('%H:%M'),
            t.paciente.nombre_completo, t.paciente.dni,
            t.paciente.obra_social.sigla if t.paciente.obra_social else 'Particular',
            t.get_estado_display(), float(t.monto_coseguro) if t.monto_coseguro else 0,
            t.establecimiento.nombre if t.establecimiento else '—'
        ])
    
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename=turnos_{inicio.strftime("%Y%m%d")}_{fin.strftime("%Y%m%d")}.xlsx'
    wb.save(response)
    return response

@login_required
def cobranza_os(request):
    if request.user.rol not in ['profesional', 'secretaria']:
        return redirect('home')
    
    if request.user.rol == 'secretaria':
        establecimiento = request.user.establecimiento
        profesional_id = request.GET.get('profesional')
        if profesional_id:
            profesional = get_object_or_404(Profesional, id=profesional_id)
        else:
            profesional = Profesional.objects.filter(establecimientos=establecimiento, activo=True).first()
        establecimiento_filtro = establecimiento
    else:
        profesional = get_object_or_404(Profesional, usuario=request.user)
        establecimiento_filtro = _get_establecimiento_activo(request, profesional)
    
    hoy = date.today()
    mes_str = request.GET.get('mes', hoy.strftime('%Y-%m'))
    try:
        inicio = datetime.strptime(mes_str + '-01', '%Y-%m-%d').date()
    except:
        inicio = hoy.replace(day=1)
    fin = (inicio + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    
    # Todos los turnos completados que tienen algún monto registrado
    turnos = TurnoProfesional.objects.filter(
        profesional=profesional,
        fecha__range=[inicio, fin],
        estado='completado',
    ).filter(
        Q(monto_os__gt=0) | Q(monto_total__isnull=False)
    )
    if establecimiento_filtro:
        turnos = turnos.filter(establecimiento=establecimiento_filtro)
    turnos = turnos.order_by('-fecha')
    
    # Totales de OS
    turnos_os = turnos.filter(monto_os__gt=0)
    total_facturado_os = turnos_os.aggregate(Sum('monto_os'))['monto_os__sum'] or 0
    total_cobrado_os = turnos_os.filter(os_cobrado=True).aggregate(Sum('monto_os'))['monto_os__sum'] or 0
    total_pendiente_os = total_facturado_os - total_cobrado_os

    # Totales de particulares
    turnos_particulares = turnos.filter(monto_os__isnull=True) | turnos.filter(monto_os=0)
    total_facturado_particulares = turnos_particulares.aggregate(Sum('monto_total'))['monto_total__sum'] or 0
    # En particulares se asume que están cobrados al momento, por lo que coinciden facturado y cobrado
    total_cobrado_particulares = total_facturado_particulares
    
    mes_anterior = (inicio - timedelta(days=1)).strftime('%Y-%m')
    mes_siguiente = (inicio + timedelta(days=32)).strftime('%Y-%m')
    
    return render(request, 'turnos_profesionales/cobranza_os.html', {
        'turnos': turnos,
        'inicio': inicio, 'fin': fin,
        'total_facturado_os': total_facturado_os,
        'total_cobrado_os': total_cobrado_os,
        'total_pendiente_os': total_pendiente_os,
        'total_facturado_particulares': total_facturado_particulares,
        'total_cobrado_particulares': total_cobrado_particulares,
        'mes_anterior': mes_anterior,
        'mes_siguiente': mes_siguiente,
    })

@login_required
def marcar_cobrado_os(request, turno_id):
    turno = get_object_or_404(TurnoProfesional, id=turno_id)
    turno.os_cobrado = True
    turno.fecha_cobro_os = date.today()
    turno.save()
    messages.success(request, '✅ Cobro de OS registrado.')
    return redirect('cobranza_os')

@login_required
def reserva_multiple(request):
    if request.user.rol not in ['profesional', 'secretaria']:
        return redirect('home')
    
    if request.user.rol == 'secretaria':
        profesional_id = request.GET.get('profesional')
        if profesional_id:
            profesional = get_object_or_404(Profesional, id=profesional_id)
        else:
            profesional = Profesional.objects.filter(
                establecimientos=request.user.establecimiento, activo=True
            ).first()
        establecimiento_filtro = request.user.establecimiento
    else:
        profesional = get_object_or_404(Profesional, usuario=request.user)
        establecimiento_filtro = _get_establecimiento_activo(request, profesional)
    
    paciente_seleccionado = None
    paciente_id = request.GET.get('paciente_id')
    if paciente_id:
        paciente_seleccionado = get_object_or_404(Paciente, id=paciente_id)
    
    dias_semana = [
        (0, 'Lunes'), (1, 'Martes'), (2, 'Miércoles'),
        (3, 'Jueves'), (4, 'Viernes')
    ]
    
    if request.method == 'POST':
        paciente_id = request.POST.get('paciente_id')
        dias = request.POST.getlist('dias')
        semanas = int(request.POST.get('semanas', 4))
        tipo_consulta = request.POST.get('tipo_consulta', '').strip()
        
        paciente = get_object_or_404(Paciente, id=paciente_id)
        establecimiento = establecimiento_filtro if establecimiento_filtro else profesional.establecimientos.first()
        hoy = date.today()
        turnos_creados = 0
        
        for semana in range(semanas):
            for dia_str in dias:
                dia = int(dia_str)
                hora_str = request.POST.get(f'hora_{dia}')
                hora = datetime.strptime(hora_str, '%H:%M').time()
                
                fecha = hoy + timedelta(weeks=semana)
                dias_hasta = (dia - fecha.weekday()) % 7
                fecha += timedelta(days=dias_hasta)
                
                if fecha < hoy:
                    continue
                
                agenda = Agenda.objects.filter(
                    profesional=profesional, activo=True, fecha_inicio__lte=fecha
                )
                if establecimiento_filtro:
                    agenda = agenda.filter(establecimiento=establecimiento_filtro)
                agenda = agenda.first()
                
                duracion = 30
                slot_disponible = False
                if agenda:
                    horario = HorarioAtencion.objects.filter(agenda=agenda, dia=fecha.weekday()).first()
                    if horario:
                        duracion = horario.duracion_turno
                        ocupados = TurnoProfesional.objects.filter(
                            profesional=profesional,
                            establecimiento=establecimiento,
                            fecha=fecha,
                            hora_inicio=hora,
                            estado__in=['pendiente', 'confirmado']
                        ).count()
                        if ocupados < agenda.pacientes_simultaneos:
                            slot_disponible = True
                
                hora_fin = (datetime.combine(fecha, hora) + timedelta(minutes=duracion)).time()
                
                TurnoProfesional.objects.create(
                    profesional=profesional,
                    establecimiento=establecimiento,
                    paciente=paciente,
                    fecha=fecha,
                    hora_inicio=hora,
                    hora_fin=hora_fin,
                    estado='pendiente',
                    tipo_consulta=tipo_consulta if tipo_consulta else 'Reserva múltiple',
                    es_sobreturno=not slot_disponible,
                )
                turnos_creados += 1
        
        messages.success(request, f'✅ {turnos_creados} turnos creados para {paciente.nombre_completo}.')
        return redirect('panel_profesional')
    
    return render(request, 'turnos_profesionales/reserva_multiple.html', {
        'profesional': profesional,
        'paciente_seleccionado': paciente_seleccionado,
        'dias_semana': dias_semana,
    })


@login_required
def atender_igual(request, turno_id):
    turno = get_object_or_404(TurnoProfesional, id=turno_id)
    if request.user.rol not in ['profesional', 'secretaria']:
        messages.error(request, 'No tenés permiso.')
        return redirect('panel_profesional')

    if turno.estado != 'no_asistio' or not turno.no_asistio_automatico:
        messages.error(request, 'Este turno no puede ser atendido de esta manera.')
        return redirect('panel_profesional')

    # Restaurar sesión si se había descontado
    if turno.sesion_descontada:
        os_paciente = PacienteObraSocial.objects.filter(
            paciente=turno.paciente,
            activa=True,
            profesional=turno.profesional,
        ).first()
        if os_paciente:
            os_paciente.sesiones_restantes += 1
            os_paciente.save()
            turno.sesion_descontada = False

    turno.estado = 'pendiente'
    turno.no_asistio_automatico = False
    turno.save()

    messages.success(request, f'El turno de {turno.paciente.nombre_completo} fue reactivado. Podés atenderlo.')
    if request.user.rol == 'secretaria':
        return redirect('panel_secretaria')
    return redirect('panel_profesional')




    