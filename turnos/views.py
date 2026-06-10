from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from datetime import date, timedelta, datetime
from .models import Turno
from profesionales.models import Profesional
from agendas.models import Agenda, HorarioAtencion, BloqueoAgenda
from agendas import models
from django.db.models import Q


@login_required
def confirmar_turno(request, turno_id):
    turno = get_object_or_404(Turno, id=turno_id)
    
    # Verificar que el profesional sea el dueño del turno
    if request.user != turno.profesional.usuario:
        messages.error(request, 'No tenés permiso para modificar este turno.')
        return redirect('panel_profesional')
    
    turno.estado = 'confirmado'
    turno.save()
    messages.success(request, f'Turno de las {turno.hora_inicio.strftime("%H:%M")} confirmado.')
    
    return redirect('panel_profesional')


@login_required
def cancelar_turno(request, turno_id):
    turno = get_object_or_404(Turno, id=turno_id)
    
    if request.user != turno.profesional.usuario:
        messages.error(request, 'No tenés permiso para modificar este turno.')
        return redirect('panel_profesional')
    
    turno.estado = 'cancelado'
    turno.save()
    messages.warning(request, f'Turno de las {turno.hora_inicio.strftime("%H:%M")} cancelado.')
    
    return redirect('panel_profesional')


@login_required
def completar_turno(request, turno_id):
    turno = get_object_or_404(Turno, id=turno_id)
    
    if request.user != turno.profesional.usuario:
        messages.error(request, 'No tenés permiso para modificar este turno.')
        return redirect('panel_profesional')
    
    turno.estado = 'completado'
    turno.save()
    messages.success(request, f'Turno de las {turno.hora_inicio.strftime("%H:%M")} marcado como completado.')
    
    return redirect('panel_profesional')


@login_required
def no_asistio_turno(request, turno_id):
    turno = get_object_or_404(Turno, id=turno_id)
    
    if request.user != turno.profesional.usuario:
        messages.error(request, 'No tenés permiso para modificar este turno.')
        return redirect('panel_profesional')
    
    turno.estado = 'no_asistio'
    turno.save()
    messages.warning(request, f'Paciente marcado como "No Asistió" al turno de las {turno.hora_inicio.strftime("%H:%M")}.')
    
    return redirect('panel_profesional')



def sacar_turno_rapido(request, profesional_id=None):
    """
    Formulario público para sacar turno sin registro.
    Si no se especifica profesional, se muestra lista de profesionales.
    """
    # Si viene un profesional específico
    if profesional_id:
        profesional = get_object_or_404(Profesional, id=profesional_id, activo=True)
        return mostrar_formulario_turno(request, profesional)
    
    # Si no, mostrar lista de profesionales disponibles
    profesionales = Profesional.objects.filter(activo=True)
    
    return render(request, 'turnos/elegir_profesional.html', {
        'profesionales': profesionales
    })


def mostrar_formulario_turno(request, profesional):
    """Muestra el formulario para elegir fecha y hora"""
    hoy = date.today()
    
    if request.method == 'POST':
        # Procesar el turno solicitado
        fecha_str = request.POST.get('fecha')
        hora_str = request.POST.get('hora')
        nombre = request.POST.get('nombre')
        telefono = request.POST.get('telefono')
        motivo = request.POST.get('motivo', '')
        
        # Validar datos
        if not all([fecha_str, hora_str, nombre, telefono]):
            messages.error(request, 'Completá todos los campos obligatorios.')
            return redirect('sacar_turno_profesional', profesional_id=profesional.id)
        
        try:
            fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
            hora = datetime.strptime(hora_str, '%H:%M').time()
        except ValueError:
            messages.error(request, 'Fecha u hora inválida.')
            return redirect('sacar_turno_profesional', profesional_id=profesional.id)
        
        # Validar que la fecha no sea pasada
        if fecha < hoy:
            messages.error(request, 'No podés sacar turno para una fecha pasada.')
            return redirect('sacar_turno_profesional', profesional_id=profesional.id)
        
        # Verificar disponibilidad
        if not verificar_disponibilidad(profesional, fecha, hora):
            messages.error(request, 'Ese horario no está disponible. Elegí otro.')
            return redirect('sacar_turno_profesional', profesional_id=profesional.id)
        
        # Crear el turno
        duracion = obtener_duracion_turno(profesional, fecha, hora)
        hora_fin = (datetime.combine(fecha, hora) + timedelta(minutes=duracion)).time()
        
        Turno.objects.create(
            profesional=profesional,
            fecha=fecha,
            hora_inicio=hora,
            hora_fin=hora_fin,
            estado='pendiente',
            nombre_no_registrado=nombre,
            telefono_no_registrado=telefono,
            motivo_consulta=motivo,
            enviar_recordatorio=True
        )
        
        messages.success(request, f'¡Turno reservado! {nombre}, tu turno es el {fecha.strftime("%d/%m/%Y")} a las {hora_str}.')
        return redirect('home')
    
    # GET - Mostrar formulario con horarios disponibles
    dias_disponibles = obtener_dias_disponibles(profesional, hoy)
    
    return render(request, 'turnos/sacar_turno.html', {
        'profesional': profesional,
        'dias_disponibles': dias_disponibles,
        'hoy': hoy
    })


def verificar_disponibilidad(profesional, fecha, hora):
    """Verifica si un horario está disponible"""
    # Verificar que el profesional atienda ese día y horario
    agenda = Agenda.objects.filter(
        profesional=profesional,
        activo=True,
        fecha_inicio__lte=fecha,
    ).filter(
        Q(fecha_fin__isnull=True) | Q(fecha_fin__gte=fecha)
    ).first()
    
    if not agenda:
        return False
    
    dia_semana = fecha.weekday()  # 0=Lunes, 6=Domingo
    horario = HorarioAtencion.objects.filter(
        agenda=agenda,
        dia=dia_semana,
        hora_inicio__lte=hora,
        hora_fin__gt=hora
    ).first()
    
    if not horario:
        return False
    
    # Verificar que no esté bloqueado
    bloqueo = BloqueoAgenda.objects.filter(
        agenda=agenda,
        fecha=fecha,
        activo=True
    )
    if bloqueo.exists():
        return False
    
    # Verificar que no haya otro turno en ese horario
    turno_existente = Turno.objects.filter(
        profesional=profesional,
        fecha=fecha,
        hora_inicio=hora,
        estado__in=['pendiente', 'confirmado']
    ).exists()
    
    if turno_existente:
        return False
    
    return True


def obtener_duracion_turno(profesional, fecha, hora):
    """Obtiene la duración del turno según la configuración"""
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
    
    return 30  # Default 30 minutos


def obtener_dias_disponibles(profesional, hoy):
    """Devuelve los próximos 30 días con disponibilidad"""
    from django.db import models
    
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
            # Generar slots disponibles para ese día
            hora_actual = horario.hora_inicio
            slots = []
            
            while hora_actual < horario.hora_fin:
                hora_fin_slot = (
                    datetime.combine(fecha, hora_actual) + 
                    timedelta(minutes=horario.duracion_turno)
                ).time()
                
                if hora_fin_slot <= horario.hora_fin:
                    # Verificar si está ocupado
                    ocupado = Turno.objects.filter(
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