from decimal import Decimal
import threading

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Count, Sum
from datetime import date, timedelta, datetime
from django.http import HttpResponse
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A5
from reportlab.lib.units import cm
from openpyxl import Workbook

from establecimientos.models import Establecimiento
from .models import TurnoProfesional, ArchivoTurno
from profesionales.models import Profesional
from pacientes.models import Paciente
from agendas.models import Agenda, HorarioAtencion, BloqueoAgenda
from historias_clinicas.models import HistoriaClinica, Evolucion, ArchivoClinico
from .google_calendar import GoogleCalendarManager


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
Sesiones restantes: {turno.paciente.sesiones_restantes or '—'}
        """
        location = turno.establecimiento.direccion if turno.establecimiento else ''
        
        attendees = []
        if turno.paciente.email:
            attendees.append(turno.paciente.email)
        if turno.profesional.email:
            attendees.append(turno.profesional.email)
        
        event = gcal.create_event(
            summary=summary,
            start_time=start_time,
            end_time=end_time,
            timezone="America/Argentina/Salta",
            attendees=attendees,
            description=description,
            location=location
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
    """Panel principal del profesional. Muestra turnos del día."""
    if request.user.rol not in ['profesional', 'secretaria']:
        messages.error(request, 'No tenés acceso a esta sección.')
        return redirect('home')
    
    if request.user.rol == 'secretaria':
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
    else:
        profesional = get_object_or_404(Profesional, usuario=request.user)
        establecimientos = profesional.establecimientos.all()
        profesionales_consultorio = None
    
    hoy = date.today()
    
    turnos_hoy = TurnoProfesional.objects.filter(
        profesional=profesional, fecha=hoy
    ).order_by('hora_inicio')
    
    manana = hoy + timedelta(days=1)
    turnos_manana = TurnoProfesional.objects.filter(
        profesional=profesional, fecha=manana
    ).order_by('hora_inicio')
    
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
    
    if paciente.sesiones_restantes is not None and paciente.sesiones_restantes > 0:
        paciente.sesiones_restantes -= 1
        paciente.save()
    
    if paciente.plan_obra_social:
        plan = paciente.plan_obra_social
        if plan.coseguro_fijo and plan.coseguro_fijo > 0:
            turno.monto_coseguro = plan.coseguro_fijo
        elif plan.coseguro_porcentaje and plan.coseguro_porcentaje > 0:
            turno.monto_coseguro = 0
    
    turno.save()
    
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
    plan = paciente.plan_obra_social
    
    if request.method == 'POST':
        monto_total = request.POST.get('monto_total', '')
        monto_os = request.POST.get('monto_os', '')
        monto_coseguro = request.POST.get('monto_coseguro', '')
        
        if monto_total:
            turno.monto_total = Decimal(monto_total)
        if monto_os:
            turno.monto_os = Decimal(monto_os)
        if monto_coseguro:
            turno.monto_coseguro = Decimal(monto_coseguro)
        
        turno.save()
        
        if turno.monto_total and turno.monto_os and not turno.monto_coseguro:
            turno.monto_coseguro = turno.monto_total - turno.monto_os
            turno.save()
        
        coseguro_msg = ''
        if turno.monto_coseguro and turno.monto_coseguro > 0:
            coseguro_msg = f' | 💰 Cobrar al paciente: ${turno.monto_coseguro}'
        
        messages.success(request, f'Cobro registrado.{coseguro_msg}')
        return redirect('panel_profesional')
    
        if request.user.rol == 'secretaria':
            return redirect('panel_secretaria')
        return redirect('cargar_evolucion', turno_id=turno.id)
    
    return render(request, 'turnos_profesionales/cobrar_turno.html', {
        'turno': turno, 'paciente': paciente, 'plan': plan
    })


@login_required
def no_asistio_turno(request, turno_id):
    turno = get_object_or_404(TurnoProfesional, id=turno_id)
    if request.user.rol not in ['profesional', 'secretaria']:
        messages.error(request, 'No tenés permiso.')
        return redirect('panel_profesional')
    
    turno.estado = 'no_asistio'
    turno.save()
    
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
        
        messages.success(request, 'Evolución cargada correctamente.')
        return redirect('cobrar_turno', turno_id=turno.id) 
    
    return render(request, 'turnos_profesionales/cargar_evolucion.html', {
        'profesional': profesional, 'turno': turno, 'historia': historia
    })


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
    else:
        profesional = get_object_or_404(Profesional, usuario=request.user)
    
    if not profesional:
        messages.error(request, 'No hay profesionales disponibles.')
        return redirect('panel_secretaria' if request.user.rol == 'secretaria' else 'home')
    
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
        
        establecimiento = None
        establecimiento_id = request.POST.get('establecimiento')
        if establecimiento_id:
            establecimiento = get_object_or_404(Establecimiento, id=establecimiento_id)
        else:
            establecimiento = profesional.establecimientos.first()
        
        turnos_en_horario = TurnoProfesional.objects.filter(
            profesional=profesional, fecha=fecha, hora_inicio=hora,
            estado__in=['pendiente', 'confirmado']
        ).count()
        
        agenda = Agenda.objects.filter(profesional=profesional, activo=True, fecha_inicio__lte=fecha).first()
        max_simultaneos = agenda.pacientes_simultaneos if agenda else 1
        
        if turnos_en_horario >= max_simultaneos:
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
        
        archivos = request.FILES.getlist('archivos')
        descripcion_archivo = request.POST.get('descripcion_archivo', '')
        for archivo in archivos:
            ArchivoTurno.objects.create(turno=turno, archivo=archivo, descripcion=descripcion_archivo)
        
        # Google Calendar
        try:
            threading.Thread(target=crear_evento_google, args=(turno,)).start()
        except:
            pass
        
        messages.success(request, f'Turno asignado a {paciente.nombre_completo} el {fecha.strftime("%d/%m/%Y")} a las {hora_str}.')
        
        if request.user.rol == 'secretaria':
            return redirect('panel_secretaria')
        return redirect('panel_profesional')
    
    # GET
    dias_disponibles = []
    agenda = Agenda.objects.filter(profesional=profesional, activo=True, fecha_inicio__lte=hoy + timedelta(days=30)).first()
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
                        ).count()
                        if ocupados < max_simultaneos:
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
    })


# ============ EDITAR TURNO ============

@login_required
def editar_turno(request, turno_id):
    if request.user.rol not in ['profesional', 'secretaria']:
        return redirect('home')
    
    turno = get_object_or_404(TurnoProfesional, id=turno_id)
    
    if request.user.rol == 'secretaria':
        profesional = turno.profesional
    else:
        profesional = get_object_or_404(Profesional, usuario=request.user)
        if request.user != turno.profesional.usuario:
            messages.error(request, 'No tenés permiso.')
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
        
        if fecha != turno.fecha or hora != turno.hora_inicio:
            existe = TurnoProfesional.objects.filter(
                profesional=profesional, fecha=fecha, hora_inicio=hora,
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
        
        agenda = Agenda.objects.filter(
            profesional=profesional, activo=True, fecha_inicio__lte=fecha
        ).filter(Q(fecha_fin__isnull=True) | Q(fecha_fin__gte=fecha)).first()
        
        duracion = 30
        if agenda:
            horario_atencion = HorarioAtencion.objects.filter(agenda=agenda, dia=fecha.weekday()).first()
            if horario_atencion:
                duracion = horario_atencion.duracion_turno
        
        turno.hora_fin = (datetime.combine(fecha, hora) + timedelta(minutes=duracion)).time()
        turno.save()
        
        # Archivos
        archivos = request.FILES.getlist('archivos')
        descripcion_archivo = request.POST.get('descripcion_archivo', '')
        for archivo in archivos:
            ArchivoTurno.objects.create(turno=turno, archivo=archivo, descripcion=descripcion_archivo)
        
        # Google Calendar: eliminar viejo y crear nuevo
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
    agenda = Agenda.objects.filter(profesional=profesional, activo=True, fecha_inicio__lte=hoy + timedelta(days=30)).first()
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
                        ).exclude(id=turno.id).exists()
                        if not ocupado or (fecha == turno.fecha and hora_actual == turno.hora_inicio):
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
                establecimientos=request.user.establecimiento, activo=True
            ).first()
            if not profesional:
                messages.error(request, 'No hay profesionales en el consultorio.')
                return redirect('panel_secretaria')
            

@login_required
def calendario_semanal(request):
    if request.user.rol not in ['profesional', 'secretaria']:
        return redirect('home')
    
    # Determinar profesional según el rol
    if request.user.rol == 'secretaria':
        profesional_id = request.GET.get('profesional')
        if profesional_id:
            profesional = get_object_or_404(Profesional, id=profesional_id)
        else:
            profesional = Profesional.objects.filter(
                establecimientos=request.user.establecimiento, activo=True
            ).first()
            if not profesional:
                messages.error(request, 'No hay profesionales en el consultorio.')
                return redirect('panel_secretaria')
    else:
        profesional = get_object_or_404(Profesional, usuario=request.user)
    
    # Fecha base
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
    
    agendas = Agenda.objects.filter(
        profesional=profesional, activo=True
    ).select_related('establecimiento')
    
    for i in range(7):
        dia = lunes + timedelta(days=i)
        turnos_dia = TurnoProfesional.objects.filter(
            profesional=profesional, fecha=dia
        ).order_by('hora_inicio')
        
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
                            slot_bloqueado = False
                            for b in bloqueos:
                                if b.hora_inicio and b.hora_fin:
                                    if hora_actual >= b.hora_inicio and hora_fin_slot <= b.hora_fin:
                                        slot_bloqueado = True
                                        break
                            
                            if not slot_bloqueado:
                                turnos_en_horario = [t for t in turnos_dia if t.hora_inicio == hora_actual]
                                if turnos_en_horario:
                                    for turno in turnos_en_horario:
                                        horarios_por_consultorio[est_nombre].append({
                                            'hora_inicio': hora_actual,
                                            'hora_fin': hora_fin_slot,
                                            'turno': turno,
                                            'disponible': False,
                                            'lugares_restantes': 0,
                                        })
                                else:
                                    horarios_por_consultorio[est_nombre].append({
                                        'hora_inicio': hora_actual,
                                        'hora_fin': hora_fin_slot,
                                        'turno': None,
                                        'disponible': True,
                                        'lugares_restantes': agenda.pacientes_simultaneos,
                                    })
                        hora_actual = hora_fin_slot
        
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
            establecimientos=request.user.establecimiento, activo=True
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
    
    establecimiento = profesional.establecimientos.first()
    
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
    
    duracion = 30
    agenda = Agenda.objects.filter(profesional=profesional, activo=True, fecha_inicio__lte=fecha).filter(
        Q(fecha_fin__isnull=True) | Q(fecha_fin__gte=fecha)
    ).first()
    if agenda:
        horario_atencion = HorarioAtencion.objects.filter(agenda=agenda, dia=fecha.weekday()).first()
        if horario_atencion:
            duracion = horario_atencion.duracion_turno
    
    hora_fin = (datetime.combine(fecha, hora) + timedelta(minutes=duracion)).time()
    
    if request.method == 'POST':
        paciente_id = request.POST.get('paciente_id')
        tipo_consulta = request.POST.get('tipo_consulta', '')
        notas = request.POST.get('notas', '')
        
        if not paciente_id:
            messages.error(request, 'Seleccioná un paciente.')
            url = f'{request.path}?fecha={fecha_str}&hora={hora_str}'
            return redirect(url)
        
        paciente = get_object_or_404(Paciente, id=paciente_id)
        
        turnos_en_horario = TurnoProfesional.objects.filter(
            profesional=profesional, fecha=fecha, hora_inicio=hora,
            estado__in=['pendiente', 'confirmado']
        ).count()
        
        max_simultaneos = agenda.pacientes_simultaneos if agenda else 1
        
        if turnos_en_horario >= max_simultaneos:
            messages.error(request, f'Horario completo (máx. {max_simultaneos} pacientes).')
            return redirect('calendario_semanal')
        
        turno = TurnoProfesional.objects.create(
            profesional=profesional, establecimiento=establecimiento,
            paciente=paciente, fecha=fecha, hora_inicio=hora,
            hora_fin=hora_fin, estado='pendiente',
            tipo_consulta=tipo_consulta, notas_internas=notas
        )
        
        # Google Calendar
        try:
            threading.Thread(target=crear_evento_google, args=(turno,)).start()
        except:
            pass
        
        messages.success(request, f'Turno asignado a {paciente.nombre_completo} el {fecha.strftime("%d/%m/%Y")} a las {hora_str}.')
        return redirect('calendario_semanal')
    
    busqueda = request.GET.get('buscar', '')
    pacientes = []
    if busqueda:
        pacientes = Paciente.objects.filter(
            Q(nombre__icontains=busqueda) | Q(apellido__icontains=busqueda) | Q(dni__icontains=busqueda)
        )[:15]
    
    return render(request, 'turnos_profesionales/asignar_calendario.html', {
        'profesional': profesional, 'fecha': fecha, 'hora': hora,
        'hora_fin': hora_fin, 'fecha_str': fecha_str, 'hora_str': hora_str,
        'pacientes': pacientes, 'busqueda': busqueda
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
        
        agenda = Agenda.objects.filter(profesional=profesional, activo=True, fecha_inicio__lte=fecha_date).filter(
            Q(fecha_fin__isnull=True) | Q(fecha_fin__gte=fecha_date)
        ).first()
        
        if not agenda:
            messages.error(request, 'No tenés agenda configurada para esa fecha.')
            return redirect('calendario_semanal')
        
        BloqueoAgenda.objects.create(
            agenda=agenda, fecha=fecha_date,
            hora_inicio=datetime.strptime(hora_inicio, '%H:%M').time() if hora_inicio and not dia_completo else None,
            hora_fin=datetime.strptime(hora_fin, '%H:%M').time() if hora_fin and not dia_completo else None,
            motivo=motivo if motivo else 'Día no laborable'
        )
        
        messages.success(request, f'Día {fecha_date.strftime("%d/%m/%Y")} bloqueado.')
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
    
    if profesional_seleccionado:
        turnos_hoy = TurnoProfesional.objects.filter(profesional=profesional_seleccionado, fecha=hoy).order_by('hora_inicio')
    else:
        turnos_hoy = TurnoProfesional.objects.filter(
            profesional__in=profesionales, establecimiento=establecimiento, fecha=hoy
        ).order_by('profesional', 'hora_inicio')
    
    total_hoy = turnos_hoy.count()
    pendientes = turnos_hoy.filter(estado='pendiente').count()
    confirmados = turnos_hoy.filter(estado='confirmado').count()
    en_sala = turnos_hoy.filter(estado='en_sala').count()
    
    return render(request, 'turnos_profesionales/panel_secretaria.html', {
        'profesionales': profesionales, 'profesional_seleccionado': profesional_seleccionado,
        'turnos_hoy': turnos_hoy, 'hoy': hoy, 'total_hoy': total_hoy,
        'pendientes': pendientes, 'confirmados': confirmados, 'en_sala': en_sala,
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
    else:
        profesional = get_object_or_404(Profesional, usuario=request.user)
        if request.user != turno.profesional.usuario:
            messages.error(request, 'No tenés permiso.')
            return redirect('panel_profesional')
    
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
        
        if nueva_fecha < hoy:
            messages.error(request, 'No podés reprogramar a una fecha pasada.')
            return redirect('reprogramar_turno', turno_id=turno.id)
        
        existe = TurnoProfesional.objects.filter(
            profesional=profesional, fecha=nueva_fecha, hora_inicio=nueva_hora,
            estado__in=['pendiente', 'confirmado']
        ).exclude(id=turno.id).exists()
        
        if existe:
            messages.error(request, 'Ese horario ya está ocupado.')
            return redirect('reprogramar_turno', turno_id=turno.id)
        
        if establecimiento_id:
            turno.establecimiento = get_object_or_404(Establecimiento, id=establecimiento_id)
        
        fecha_anterior = turno.fecha
        hora_anterior = turno.hora_inicio
        
        turno.fecha = nueva_fecha
        turno.hora_inicio = nueva_hora
        
        duracion = 30
        agenda = Agenda.objects.filter(profesional=profesional, activo=True, fecha_inicio__lte=nueva_fecha).filter(
            Q(fecha_fin__isnull=True) | Q(fecha_fin__gte=nueva_fecha)
        ).first()
        if agenda:
            horario_atencion = HorarioAtencion.objects.filter(agenda=agenda, dia=nueva_fecha.weekday()).first()
            if horario_atencion:
                duracion = horario_atencion.duracion_turno
        
        turno.hora_fin = (datetime.combine(nueva_fecha, nueva_hora) + timedelta(minutes=duracion)).time()
        turno.save()
        
        # Google Calendar
        try:
            threading.Thread(target=eliminar_evento_google, args=(turno,)).start()
            threading.Thread(target=crear_evento_google, args=(turno,)).start()
        except:
            pass
        
        messages.success(request, 
            f'Turno reprogramado del {fecha_anterior.strftime("%d/%m/%Y")} {hora_anterior.strftime("%H:%M")} → {nueva_fecha.strftime("%d/%m/%Y")} {nueva_hora.strftime("%H:%M")}.')
        
        if request.user.rol == 'secretaria':
            return redirect('panel_secretaria')
        return redirect('panel_profesional')
    
    # GET
    dias_disponibles = []
    agenda = Agenda.objects.filter(profesional=profesional, activo=True, fecha_inicio__lte=hoy + timedelta(days=30)).first()
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
                        ).exclude(id=turno.id).exists()
                        if not ocupado:
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
    else:
        profesional = get_object_or_404(Profesional, usuario=request.user)
    
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
            establecimiento = profesional.establecimientos.first()
        
        turno = TurnoProfesional.objects.create(
            profesional=profesional, establecimiento=establecimiento,
            paciente=paciente, fecha=fecha, hora_inicio=hora,
            hora_fin=hora_fin, estado='confirmado',
            tipo_consulta=tipo_consulta, notas_internas=notas, es_sobreturno=True
        )
        
        # Google Calendar
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
    else:
        profesional = get_object_or_404(Profesional, usuario=request.user)
    
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
        
        try:
            fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
            hora = datetime.strptime(hora_str, '%H:%M').time()
            hora_fin = datetime.strptime(hora_fin_str, '%H:%M').time() if hora_fin_str else (
                datetime.combine(fecha, hora) + timedelta(minutes=15)
            ).time()
        except ValueError:
            messages.error(request, 'Fecha u hora inválida.')
            return redirect('calendario_semanal')
        
        establecimiento = None
        if establecimiento_id:
            establecimiento = get_object_or_404(Establecimiento, id=establecimiento_id)
        else:
            establecimiento = profesional.establecimientos.first()
        
        turno = TurnoProfesional.objects.create(
            profesional=profesional, establecimiento=establecimiento,
            paciente=paciente, fecha=fecha, hora_inicio=hora,
            hora_fin=hora_fin, estado='confirmado',
            tipo_consulta=tipo_consulta, notas_internas=notas, es_sobreturno=True
        )
        
        # Google Calendar
        try:
            threading.Thread(target=crear_evento_google, args=(turno,)).start()
        except:
            pass
        
        messages.success(request, f'🚨 Sobreturno creado para {paciente.nombre_completo}.')
        return redirect('calendario_semanal')
    
    busqueda = request.GET.get('buscar', '')
    pacientes = []
    if busqueda:
        pacientes = Paciente.objects.filter(
            Q(nombre__icontains=busqueda) | Q(apellido__icontains=busqueda) | Q(dni__icontains=busqueda)
        )[:15]
    
    return render(request, 'turnos_profesionales/sobreturno_calendario.html', {
        'profesional': profesional, 'fecha_str': fecha_str,
        'hora_str': hora_str, 'hora_fin_str': hora_fin_str,
        'pacientes': pacientes, 'busqueda': busqueda
    })


# ============ RECETA PDF ============

@login_required
def generar_receta(request, evolucion_id):
    evolucion = get_object_or_404(Evolucion, id=evolucion_id)
    paciente = evolucion.historia_clinica.paciente
    profesional = evolucion.profesional
    
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="receta_{paciente.apellido}_{evolucion.creado.strftime("%Y%m%d")}.pdf"'
    
    p = canvas.Canvas(response, pagesize=A5)
    width, height = A5
    
    p.setFont("Helvetica-Bold", 16)
    p.drawString(2*cm, height - 2*cm, "RECETA MÉDICA")
    p.line(2*cm, height - 2.3*cm, width - 2*cm, height - 2.3*cm)
    
    p.setFont("Helvetica-Bold", 11)
    p.drawString(2*cm, height - 3*cm, f"Profesional: {profesional.nombre_completo}")
    p.setFont("Helvetica", 10)
    p.drawString(2*cm, height - 3.5*cm, f"Especialidad: {profesional.get_especialidad_display()}")
    p.drawString(2*cm, height - 4*cm, f"Matrícula: {profesional.matricula}")
    
    p.setFont("Helvetica-Bold", 11)
    p.drawString(2*cm, height - 5*cm, f"Paciente: {paciente.nombre_completo}")
    p.setFont("Helvetica", 10)
    p.drawString(2*cm, height - 5.5*cm, f"DNI: {paciente.dni}")
    p.drawString(2*cm, height - 6*cm, f"Fecha: {evolucion.creado.strftime('%d/%m/%Y')}")
    
    p.setFont("Helvetica-Bold", 11)
    p.drawString(2*cm, height - 7*cm, "Diagnóstico:")
    p.setFont("Helvetica", 10)
    p.drawString(2*cm, height - 7.5*cm, evolucion.diagnostico or "No especificado")
    
    p.setFont("Helvetica-Bold", 11)
    p.drawString(2*cm, height - 9*cm, "Medicación Recetada:")
    p.setFont("Helvetica", 10)
    y = height - 9.5*cm
    for linea in (evolucion.medicacion_recetada or "No se recetó medicación").split('\n'):
        p.drawString(2*cm, y, linea.strip())
        y -= 0.5*cm
    
    if evolucion.indicaciones:
        y -= 0.5*cm
        p.setFont("Helvetica-Bold", 11)
        p.drawString(2*cm, y, "Indicaciones:")
        p.setFont("Helvetica", 10)
        y -= 0.5*cm
        for linea in evolucion.indicaciones.split('\n'):
            p.drawString(2*cm, y, linea.strip())
            y -= 0.5*cm
    
    p.line(2*cm, 4*cm, 8*cm, 4*cm)
    p.setFont("Helvetica", 8)
    p.drawString(2*cm, 3.5*cm, f"Dr/a. {profesional.nombre_completo}")
    p.drawString(2*cm, 3.2*cm, f"Mat. {profesional.matricula}")
    
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
            turnos_base = TurnoProfesional.objects.filter(profesional=profesional_seleccionado)
        else:
            turnos_base = TurnoProfesional.objects.filter(profesional__in=profesionales)
    else:
        profesional = get_object_or_404(Profesional, usuario=request.user)
        establecimiento = None
        profesionales = None
        profesional_seleccionado = profesional
        turnos_base = TurnoProfesional.objects.filter(profesional=profesional)
    
    hoy = date.today()
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
            turnos_base = TurnoProfesional.objects.filter(profesional=profesional_seleccionado)
        else:
            turnos_base = TurnoProfesional.objects.filter(profesional__in=profesionales)
    else:
        profesional = get_object_or_404(Profesional, usuario=request.user)
        turnos_base = TurnoProfesional.objects.filter(profesional=profesional)
    
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