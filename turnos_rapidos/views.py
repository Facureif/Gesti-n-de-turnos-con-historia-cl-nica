from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from datetime import date, timedelta, datetime

from .models import TurnoRapido
from profesionales.models import Profesional
from agendas.models import Agenda, HorarioAtencion, BloqueoAgenda


# ============ PANEL PROFESIONAL RÁPIDO ============

@login_required
def panel_rapido(request):
    if request.user.rol != 'profesional':
        return redirect('home')
    
    profesional = get_object_or_404(Profesional, usuario=request.user)
    hoy = date.today()
    
    turnos_hoy = TurnoRapido.objects.filter(
        profesional=profesional,
        fecha=hoy
    ).order_by('hora_inicio')
    
    contexto = {
        'profesional': profesional,
        'hoy': hoy,
        'turnos_hoy': turnos_hoy,
        'total_hoy': turnos_hoy.count(),
        'confirmados_hoy': turnos_hoy.filter(estado='confirmado').count(),
        'pendientes_hoy': turnos_hoy.filter(estado='pendiente').count(),
        'completados_hoy': turnos_hoy.filter(estado='completado').count(),
    }
    
    return render(request, 'turnos_rapidos/panel.html', contexto)


# ============ ACCIONES DE TURNOS RÁPIDOS ============

@login_required
def confirmar_turno_rapido(request, turno_id):
    turno = get_object_or_404(TurnoRapido, id=turno_id)
    if request.user != turno.profesional.usuario:
        messages.error(request, 'No tenés permiso.')
        return redirect('panel_rapido')
    
    turno.estado = 'confirmado'
    turno.save()
    messages.success(request, f'Turno de {turno.nombre_cliente} confirmado.')
    return redirect('panel_rapido')


@login_required
def cancelar_turno_rapido(request, turno_id):
    turno = get_object_or_404(TurnoRapido, id=turno_id)
    if request.user != turno.profesional.usuario:
        messages.error(request, 'No tenés permiso.')
        return redirect('panel_rapido')
    
    turno.estado = 'cancelado'
    turno.save()
    messages.warning(request, f'Turno de {turno.nombre_cliente} cancelado.')
    return redirect('panel_rapido')


@login_required
def completar_turno_rapido(request, turno_id):
    turno = get_object_or_404(TurnoRapido, id=turno_id)
    if request.user != turno.profesional.usuario:
        messages.error(request, 'No tenés permiso.')
        return redirect('panel_rapido')
    
    turno.estado = 'completado'
    turno.save()
    messages.success(request, f'Turno de {turno.nombre_cliente} completado.')
    return redirect('panel_rapido')


@login_required
def no_asistio_turno_rapido(request, turno_id):
    turno = get_object_or_404(TurnoRapido, id=turno_id)
    if request.user != turno.profesional.usuario:
        messages.error(request, 'No tenés permiso.')
        return redirect('panel_rapido')
    
    turno.estado = 'no_asistio'
    turno.save()
    messages.warning(request, f'{turno.nombre_cliente} no asistió.')
    return redirect('panel_rapido')


# ============ FORMULARIO PÚBLICO ============

def sacar_turno_rapido(request, profesional_id=None):
    if profesional_id:
        profesional = get_object_or_404(Profesional, id=profesional_id, activo=True)
        return mostrar_formulario_rapido(request, profesional)
    
    profesionales = Profesional.objects.filter(activo=True)
    return render(request, 'turnos_rapidos/elegir_profesional.html', {
        'profesionales': profesionales
    })


def mostrar_formulario_rapido(request, profesional):
    hoy = date.today()
    
    if request.method == 'POST':
        fecha_str = request.POST.get('fecha')
        hora_str = request.POST.get('hora')
        nombre = request.POST.get('nombre')
        telefono = request.POST.get('telefono')
        nota = request.POST.get('nota', '')
        
        if not all([fecha_str, hora_str, nombre, telefono]):
            messages.error(request, 'Completá todos los campos obligatorios.')
            return redirect('sacar_turno_rapido_profesional', profesional_id=profesional.id)
        
        try:
            fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
            hora = datetime.strptime(hora_str, '%H:%M').time()
        except ValueError:
            messages.error(request, 'Fecha u hora inválida.')
            return redirect('sacar_turno_rapido_profesional', profesional_id=profesional.id)
        
        if fecha < hoy:
            messages.error(request, 'No podés sacar turno para una fecha pasada.')
            return redirect('sacar_turno_rapido_profesional', profesional_id=profesional.id)
        
        if not verificar_disponibilidad(profesional, fecha, hora):
            messages.error(request, 'Ese horario no está disponible.')
            return redirect('sacar_turno_rapido_profesional', profesional_id=profesional.id)
        
        duracion = obtener_duracion_turno(profesional, fecha, hora)
        hora_fin = (datetime.combine(fecha, hora) + timedelta(minutes=duracion)).time()
        
        TurnoRapido.objects.create(
            profesional=profesional,
            fecha=fecha,
            hora_inicio=hora,
            hora_fin=hora_fin,
            estado='pendiente',
            nombre_cliente=nombre,
            telefono_cliente=telefono,
            nota=nota,
        )
        
        messages.success(request, f'¡Turno reservado! {nombre}, tu turno es el {fecha.strftime("%d/%m/%Y")} a las {hora_str}.')
        return redirect('home')
    
    dias_disponibles = obtener_dias_disponibles(profesional, hoy)
    
    return render(request, 'turnos_rapidos/sacar_turno.html', {
        'profesional': profesional,
        'dias_disponibles': dias_disponibles,
        'hoy': hoy
    })


# ============ FUNCIONES AUXILIARES ============

def verificar_disponibilidad(profesional, fecha, hora):
    agenda = Agenda.objects.filter(
        profesional=profesional,
        activo=True,
        fecha_inicio__lte=fecha,
    ).filter(
        Q(fecha_fin__isnull=True) | Q(fecha_fin__gte=fecha)
    ).first()
    
    if not agenda:
        return False
    
    dia_semana = fecha.weekday()
    horario = HorarioAtencion.objects.filter(
        agenda=agenda,
        dia=dia_semana,
        hora_inicio__lte=hora,
        hora_fin__gt=hora
    ).first()
    
    if not horario:
        return False
    
    bloqueo = BloqueoAgenda.objects.filter(
        agenda=agenda,
        fecha=fecha,
        activo=True
    )
    if bloqueo.exists():
        return False
    
    turno_existente = TurnoRapido.objects.filter(
        profesional=profesional,
        fecha=fecha,
        hora_inicio=hora,
        estado__in=['pendiente', 'confirmado']
    ).exists()
    
    if turno_existente:
        return False
    
    return True


def obtener_duracion_turno(profesional, fecha, hora):
    agenda = Agenda.objects.filter(
        profesional=profesional,
        activo=True,
        fecha_inicio__lte=fecha
    ).first()
    
    if agenda:
        dia_semana = fecha.weekday()
        horario = HorarioAtencion.objects.filter(
            agenda=agenda,
            dia=dia_semana
        ).first()
        if horario:
            return horario.duracion_turno
    
    return 30


def obtener_dias_disponibles(profesional, hoy):
    dias = []
    agenda = Agenda.objects.filter(
        profesional=profesional,
        activo=True,
        fecha_inicio__lte=hoy + timedelta(days=30)
    ).first()
    
    if not agenda:
        return []
    
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
                hora_fin_slot = (
                    datetime.combine(fecha, hora_actual) + 
                    timedelta(minutes=horario.duracion_turno)
                ).time()
                
                if hora_fin_slot <= horario.hora_fin:
                    ocupado = TurnoRapido.objects.filter(
                        profesional=profesional,
                        fecha=fecha,
                        hora_inicio=hora_actual,
                        estado__in=['pendiente', 'confirmado']
                    ).exists()
                    
                    if not ocupado:
                        slots.append(hora_actual.strftime('%H:%M'))
                
                hora_actual = hora_fin_slot
            
            if slots:
                dias.append({
                    'fecha': fecha,
                    'fecha_str': fecha.strftime('%Y-%m-%d'),
                    'nombre_dia': fecha.strftime('%A'),
                    'slots': slots
                })
    
    return dias