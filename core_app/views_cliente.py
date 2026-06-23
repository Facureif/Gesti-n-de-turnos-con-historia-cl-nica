from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from datetime import date, timedelta, datetime
from .models import ClienteSaaS
from establecimientos.models import Establecimiento
from profesionales.models import Profesional
from turnos_profesionales.models import TurnoProfesional
from django.db.models import Q
from agendas.models import Agenda, HorarioAtencion


def portal(request, cliente_slug):
    """Portal público según el cliente SaaS."""
    cliente = get_object_or_404(ClienteSaaS, slug=cliente_slug, activo=True)
    # Guardar en sesión para que las vistas de paciente sepan desde dónde vienen
    request.session['cliente_slug'] = cliente_slug
    if cliente.tipo == 'consultorio':
        profesionales = Profesional.objects.filter(
            establecimientos=cliente.establecimiento, activo=True
        )
        contexto = {
            'cliente': cliente,
            'profesionales': profesionales,
            'modo': 'consultorio'
        }
    else:
        contexto = {
            'cliente': cliente,
            'profesional': cliente.profesional,
            'consultorios': cliente.profesional.establecimientos.all() if cliente.profesional else [],
            'modo': 'profesional'
        }
    
    return render(request, 'core_app/publico/portal.html', contexto)

def sacar_turno(request, cliente_slug, profesional_id):
    """Formulario público para sacar turno."""
    cliente = get_object_or_404(ClienteSaaS, slug=cliente_slug, activo=True)
    profesional = get_object_or_404(Profesional, id=profesional_id, activo=True)
    
    hoy = date.today()
    
    # Consultorios disponibles según el tipo de cliente
    if cliente.tipo == 'consultorio':
        consultorios_disponibles = profesional.establecimientos.filter(id=cliente.establecimiento.id)
    else:
        consultorios_disponibles = profesional.establecimientos.all()
    
    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        telefono = request.POST.get('telefono')
        email = request.POST.get('email', '')
        dni = request.POST.get('dni', '')
        fecha_str = request.POST.get('fecha')
        hora_str = request.POST.get('hora')
        establecimiento_id = request.POST.get('establecimiento')
        tipo_consulta = request.POST.get('tipo_consulta', '')
        
        if not all([nombre, telefono, fecha_str, hora_str, establecimiento_id]):
            messages.error(request, 'Completá todos los campos obligatorios.')
            return redirect('sacar_turno_cliente', cliente_slug=cliente_slug, profesional_id=profesional.id)
        
        try:
            fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
            hora = datetime.strptime(hora_str, '%H:%M').time()
        except ValueError:
            messages.error(request, 'Fecha u hora inválida.')
            return redirect('sacar_turno_cliente', cliente_slug=cliente_slug, profesional_id=profesional.id)
        
        if fecha < hoy:
            messages.error(request, 'No podés sacar turno para una fecha pasada.')
            return redirect('sacar_turno_cliente', cliente_slug=cliente_slug, profesional_id=profesional.id)
        
        establecimiento = get_object_or_404(Establecimiento, id=establecimiento_id)
        
        # Buscar agenda
        agenda = Agenda.objects.filter(
            profesional=profesional, establecimiento=establecimiento,
            activo=True, fecha_inicio__lte=fecha
        ).filter(
            Q(fecha_fin__isnull=True) | Q(fecha_fin__gte=fecha)
        ).first()
        
        if not agenda:
            messages.error(request, 'No hay agenda configurada para esta fecha y consultorio.')
            return redirect('sacar_turno_cliente', cliente_slug=cliente_slug, profesional_id=profesional.id)
        
        # Verificar que atienda ese día
        horario_dia = HorarioAtencion.objects.filter(agenda=agenda, dia=fecha.weekday()).first()
        if not horario_dia:
            messages.error(request, 'El profesional no atiende este día.')
            return redirect('sacar_turno_cliente', cliente_slug=cliente_slug, profesional_id=profesional.id)
        
        # Verificar que la hora esté dentro del horario
        hora_fin = (datetime.combine(fecha, hora) + timedelta(minutes=horario_dia.duracion_turno)).time()
        if hora > horario_dia.hora_fin or hora_fin > horario_dia.hora_fin:
            messages.error(request, 'Horario fuera del rango de atención.')
            return redirect('sacar_turno_cliente', cliente_slug=cliente_slug, profesional_id=profesional.id)
        
        # Verificar disponibilidad con pacientes simultáneos
        max_simultaneos = agenda.pacientes_simultaneos if agenda else 1
        
        turnos_en_horario = TurnoProfesional.objects.filter(
            profesional=profesional,
            establecimiento=establecimiento,
            fecha=fecha,
            hora_inicio=hora,
            estado__in=['pendiente', 'confirmado']
        ).count()
        
        if turnos_en_horario >= max_simultaneos:
            messages.error(request, f'Horario completo (máx. {max_simultaneos} pacientes).')
            return redirect('sacar_turno_cliente', cliente_slug=cliente_slug, profesional_id=profesional.id)
        
        # Buscar o crear paciente
        from pacientes.models import Paciente
        import random
        
        paciente = None
        
        if dni:
            paciente = Paciente.objects.filter(dni=dni).first()
        
        if not paciente and email:
            paciente = Paciente.objects.filter(email=email).first()
        
        if not paciente and telefono:
            paciente = Paciente.objects.filter(telefono=telefono).first()
        
        if not paciente:
            partes = nombre.strip().split()
            primer_nombre = partes[0] if partes else nombre
            apellido_temp = ' '.join(partes[1:]) if len(partes) > 1 else primer_nombre
            
            dni_final = dni if dni else f"TMP{random.randint(10000, 99999)}"
            
            # Verificar que el DNI no exista ya
            if Paciente.objects.filter(dni=dni_final).exists():
                dni_final = f"TMP{random.randint(10000, 99999)}"
            
            paciente = Paciente.objects.create(
                nombre=primer_nombre,
                apellido=apellido_temp,
                telefono=telefono,
                email=email,
                dni=dni_final,
                fecha_nacimiento=hoy.replace(year=1990)
            )
        
        # CREAR EL TURNO
        turno = TurnoProfesional.objects.create(
            profesional=profesional,
            establecimiento=establecimiento,
            paciente=paciente,
            fecha=fecha,
            hora_inicio=hora,
            hora_fin=hora_fin,
            estado='pendiente',
            tipo_consulta=tipo_consulta
        )
        
        # Google Calendar (si está configurado)
        try:
            import threading
            from turnos_profesionales.views import crear_evento_google
            threading.Thread(target=crear_evento_google, args=(turno,)).start()
        except:
            pass
        
        messages.success(request, f'¡Turno reservado! {nombre}, tu turno es el {fecha.strftime("%d/%m/%Y")} a las {hora_str} en {establecimiento.nombre}.')
        return redirect('portal_cliente', cliente_slug=cliente_slug)
    
    # GET - Mostrar horarios disponibles
    dias_disponibles = []
    for est in consultorios_disponibles:
        agenda = Agenda.objects.filter(
            profesional=profesional, establecimiento=est,
            activo=True, fecha_inicio__lte=hoy + timedelta(days=30)
        ).first()
        
        if agenda:
            max_simultaneos = agenda.pacientes_simultaneos if agenda else 1
            
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
                                profesional=profesional, establecimiento=est,
                                fecha=fecha, hora_inicio=hora_actual,
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
                            'slots': slots,
                            'establecimiento': est.nombre,
                            'establecimiento_id': est.id
                        })
    
    return render(request, 'core_app/publico/sacar_turno.html', {
        'cliente': cliente,
        'profesional': profesional,
        'dias_disponibles': dias_disponibles,
        'consultorios_disponibles': consultorios_disponibles,
        'hoy': hoy
    })