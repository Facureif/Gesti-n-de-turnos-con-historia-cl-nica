from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from datetime import date, timedelta, datetime
from .models import ClienteSaaS
from establecimientos.models import Establecimiento
from profesionales.models import Profesional
from turnos_profesionales.models import TurnoProfesional
from obras_sociales.models import ObraSocial, Plan 
from django.db.models import Q
from agendas.models import Agenda, HorarioAtencion
import random
import string

def portal(request, cliente_slug):
    cliente = get_object_or_404(ClienteSaaS, slug=cliente_slug, activo=True)
    request.session['cliente_slug'] = cliente_slug
    
    # Iconos para cada especialidad
    ICONOS_ESPECIALIDAD = {
        'odontologia': '🦷',
        'kinesiologia': '💪',
        'psicologia': '🧠',
        'nutricion': '🥗',
        'medicina_general': '🩺',
        'cardiologia': '❤️',
        'dermatologia': '🔬',
        'pediatria': '👶',
        'traumatologia': '🦴',
        'otra': '👨‍⚕️',
    }
    
    if cliente.tipo == 'consultorio':
        profesionales = Profesional.objects.filter(
            establecimientos=cliente.establecimiento, activo=True
        ).prefetch_related('agenda_set__horarios')
        
        # Armar lista de especialidades disponibles (solo las que tiene el consultorio)
        especialidades_disponibles = []
        especialidades_vistas = set()
        
        for prof in profesionales:
            codigo = prof.especialidad
            if codigo and codigo not in especialidades_vistas:
                especialidades_vistas.add(codigo)
                total = sum(1 for p in profesionales if p.especialidad == codigo)
                especialidades_disponibles.append({
                    'codigo': codigo,
                    'nombre': prof.get_especialidad_display(),
                    'icono': ICONOS_ESPECIALIDAD.get(codigo, '👨‍⚕️'),
                    'total': total,
                })
        
        # Ordenar alfabéticamente por nombre
        especialidades_disponibles.sort(key=lambda x: x['nombre'])
        
        return render(request, 'core_app/landing_consultorio.html', {
            'cliente': cliente,
            'profesionales': profesionales,
            'especialidades_disponibles': especialidades_disponibles,
        })
    else:
        profesional = cliente.profesional
        consultorios = profesional.establecimientos.all()
        for est in consultorios:
            est.agenda = Agenda.objects.filter(profesional=profesional, establecimiento=est, activo=True).first()
        
        return render(request, 'core_app/landing_profesional.html', {
            'cliente': cliente,
            'profesional': profesional,
            'consultorios': consultorios,
        })

def sacar_turno(request, cliente_slug, profesional_id):
    """Formulario público para sacar turno."""
    cliente = get_object_or_404(ClienteSaaS, slug=cliente_slug, activo=True)
    profesional = get_object_or_404(Profesional, id=profesional_id, activo=True)
    
    hoy = date.today()
    
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
        
        # ✅ NUEVOS CAMPOS
        fecha_nacimiento = request.POST.get('fecha_nacimiento', '')
        numero_afiliado = request.POST.get('numero_afiliado', '')
        obra_social_id = request.POST.get('obra_social', '')
        plan_obra_social_id = request.POST.get('plan_obra_social', '')
        
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
        
        agenda = Agenda.objects.filter(
            profesional=profesional, establecimiento=establecimiento,
            activo=True, fecha_inicio__lte=fecha
        ).filter(
            Q(fecha_fin__isnull=True) | Q(fecha_fin__gte=fecha)
        ).first()
        
        if not agenda:
            messages.error(request, 'No hay agenda configurada para esta fecha y consultorio.')
            return redirect('sacar_turno_cliente', cliente_slug=cliente_slug, profesional_id=profesional.id)
        
        horario_dia = HorarioAtencion.objects.filter(agenda=agenda, dia=fecha.weekday()).first()
        if not horario_dia:
            messages.error(request, 'El profesional no atiende este día.')
            return redirect('sacar_turno_cliente', cliente_slug=cliente_slug, profesional_id=profesional.id)
        
        hora_fin = (datetime.combine(fecha, hora) + timedelta(minutes=horario_dia.duracion_turno)).time()
        if hora > horario_dia.hora_fin or hora_fin > horario_dia.hora_fin:
            messages.error(request, 'Horario fuera del rango de atención.')
            return redirect('sacar_turno_cliente', cliente_slug=cliente_slug, profesional_id=profesional.id)
        
        max_simultaneos = agenda.pacientes_simultaneos if agenda else 1
        
        turnos_en_horario = TurnoProfesional.objects.filter(
            profesional=profesional, establecimiento=establecimiento,
            fecha=fecha, hora_inicio=hora, estado__in=['pendiente', 'confirmado']
        ).count()
        
        if turnos_en_horario >= max_simultaneos:
            messages.error(request, f'Horario completo (máx. {max_simultaneos} pacientes).')
            return redirect('sacar_turno_cliente', cliente_slug=cliente_slug, profesional_id=profesional.id)
        
        # ✅ PROCESAR OBRA SOCIAL Y PLAN
        obra_social = None
        plan_obra_social = None
        if obra_social_id and obra_social_id != 'particular':
            try:
                from obras_sociales.models import ObraSocial, Plan
                obra_social = ObraSocial.objects.get(id=obra_social_id)
                if plan_obra_social_id:
                    try:
                        plan_obra_social = Plan.objects.get(id=plan_obra_social_id, obra_social=obra_social)
                    except Plan.DoesNotExist:
                        pass
            except ObraSocial.DoesNotExist:
                pass
        
        # ✅ PROCESAR FECHA DE NACIMIENTO
        fecha_nac = None
        if fecha_nacimiento:
            try:
                fecha_nac = datetime.strptime(fecha_nacimiento, '%Y-%m-%d').date()
            except (ValueError, TypeError):
                fecha_nac = None
        
        # Preparar nombre y apellido
        partes = nombre.strip().split()
        primer_nombre = partes[0] if partes else nombre
        apellido_temp = ' '.join(partes[1:]) if len(partes) > 1 else primer_nombre
        
        # Buscar o crear paciente
        from pacientes.models import Paciente
        from usuarios.models import Usuario
        import random as random_module
        
        paciente = None
        credenciales = None
        
        if dni:
            paciente = Paciente.objects.filter(dni=dni).first()
        
        if not paciente and email:
            paciente = Paciente.objects.filter(email=email).first()
        
        if not paciente and telefono:
            paciente = Paciente.objects.filter(telefono=telefono).first()
        
        if not paciente:
            # ✅ CREAR NUEVO PACIENTE
            dni_final = dni if dni else f"TMP{random_module.randint(10000, 99999)}"
            
            if Paciente.objects.filter(dni=dni_final).exists():
                dni_final = f"TMP{random_module.randint(10000, 99999)}"
            
            paciente = Paciente.objects.create(
                nombre=primer_nombre, 
                apellido=apellido_temp,
                telefono=telefono, 
                email=email,
                dni=dni_final, 
                fecha_nacimiento=fecha_nac or hoy.replace(year=1990),
                obra_social=obra_social,
                numero_afiliado=numero_afiliado if numero_afiliado else '',
                plan_obra_social=plan_obra_social,
            )
            
            # Crear usuario automáticamente
            base_username = f"{primer_nombre.lower()}.{apellido_temp.lower()}".replace(" ", "")
            username = base_username
            if Usuario.objects.filter(username=username).exists():
                username = f"{base_username}{random_module.randint(1, 999)}"
            
            password = dni if dni and not dni_final.startswith('TMP') else ''.join(random_module.choices(string.digits, k=6))
            
            usuario = Usuario.objects.create_user(
                username=username, password=password,
                first_name=primer_nombre, last_name=apellido_temp,
                email=email or '', rol='paciente', telefono=telefono
            )
            paciente.usuario = usuario
            paciente.save()
            credenciales = (username, password)
        
        else:
            # ✅ ACTUALIZAR PACIENTE EXISTENTE CON TODOS LOS DATOS DEL FORMULARIO
            paciente.nombre = primer_nombre
            paciente.apellido = apellido_temp
            paciente.telefono = telefono
            if email:
                paciente.email = email
            if dni:
                paciente.dni = dni
            if fecha_nac:
                paciente.fecha_nacimiento = fecha_nac
            if obra_social:
                paciente.obra_social = obra_social
            if numero_afiliado:
                paciente.numero_afiliado = numero_afiliado
            if plan_obra_social:
                paciente.plan_obra_social = plan_obra_social
            paciente.save()
            
            # Crear usuario si no tiene
            if not paciente.usuario:
                base_username = f"{primer_nombre.lower()}.{apellido_temp.lower()}".replace(" ", "")
                username = base_username
                if Usuario.objects.filter(username=username).exists():
                    username = f"{base_username}{random_module.randint(1, 999)}"
                
                password = paciente.dni if paciente.dni and not paciente.dni.startswith('TMP') else ''.join(random_module.choices(string.digits, k=6))
                
                usuario = Usuario.objects.create_user(
                    username=username, password=password,
                    first_name=primer_nombre, last_name=apellido_temp,
                    email=paciente.email or '', rol='paciente', telefono=paciente.telefono
                )
                paciente.usuario = usuario
                paciente.save()
                credenciales = (username, password)
        
        # Crear el turno
        turno = TurnoProfesional.objects.create(
            profesional=profesional, establecimiento=establecimiento,
            paciente=paciente, fecha=fecha, hora_inicio=hora,
            hora_fin=hora_fin, estado='pendiente', tipo_consulta=tipo_consulta
        )
        
        # Google Calendar
        try:
            import threading
            from turnos_profesionales.views import crear_evento_google
            threading.Thread(target=crear_evento_google, args=(turno,)).start()
        except:
            pass
        
        # Enviar email con credenciales si corresponde
        if credenciales and email:
            try:
                from django.core.mail import send_mail
                send_mail(
                    subject=f'Turno confirmado - {cliente.nombre}',
                    message=(
                        f'Hola {nombre}!\n\n'
                        f'Tu turno fue reservado correctamente:\n'
                        f'📅 Fecha: {fecha.strftime("%d/%m/%Y")}\n'
                        f'⏰ Hora: {hora_str}\n'
                        f'🏥 Consultorio: {establecimiento.nombre}\n'
                        f'👨‍⚕️ Profesional: {profesional.nombre_completo}\n'
                        f'🩺 Obra Social: {obra_social.nombre if obra_social else "Particular"}\n'
                        f'📋 Plan: {plan_obra_social.nombre if plan_obra_social else "N/A"}\n'
                        f'🔢 N° Afiliado: {numero_afiliado if numero_afiliado else "N/A"}\n\n'
                        f'Podés gestionar tus turnos desde tu panel personal:\n'
                        f'🔑 Usuario: {credenciales[0]}\n'
                        f'🔒 Contraseña: {credenciales[1]}\n\n'
                        f'Ingresá en: http://127.0.0.1:8000/usuarios/login/\n\n'
                        f'¡Gracias por confiar en nosotros!'
                    ),
                    from_email=None,
                    recipient_list=[email],
                    fail_silently=True,
                )
            except:
                pass
        
        # Mensaje de éxito
        if credenciales:
            messages.success(request, 
                f'¡Turno reservado!\n\n'
                f'{nombre}, tu turno es el {fecha.strftime("%d/%m/%Y")} a las {hora_str} en {establecimiento.nombre}.\n\n'
                f'📱 Te enviamos un email con tus datos de acceso a {email}.\n'
                f'🔑 Usuario: {credenciales[0]}\n'
                f'🔒 Contraseña: {credenciales[1]}'
            )
        else:
            messages.success(request, 
                f'¡Turno reservado! {nombre}, tu turno es el {fecha.strftime("%d/%m/%Y")} a las {hora_str} en {establecimiento.nombre}.\n'
                f'Ingresá a tu panel con tu usuario habitual.'
            )
        
        return redirect('portal_cliente', cliente_slug=cliente_slug)
    
    # GET
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
                            'fecha': fecha, 'fecha_str': fecha.strftime('%Y-%m-%d'),
                            'nombre_dia': fecha.strftime('%A'), 'slots': slots,
                            'establecimiento': est.nombre, 'establecimiento_id': est.id
                        })
    
    # ✅ OBTENER SOLO LAS OBRAS SOCIALES CON LAS QUE TRABAJA EL PROFESIONAL
    from obras_sociales.models import ObraSocial
    # Si el profesional tiene configuradas obras sociales, mostrar esas
    # Si no tiene ninguna configurada, mostrar todas (asume que atiende todas)
    if profesional.obras_sociales.exists():
        obras_sociales = profesional.obras_sociales.filter(activo=True).prefetch_related('planes')
    else:
        obras_sociales = ObraSocial.objects.filter(activo=True).prefetch_related('planes')
    
    return render(request, 'core_app/publico/sacar_turno.html', {
        'cliente': cliente, 'profesional': profesional,
        'dias_disponibles': dias_disponibles,
        'consultorios_disponibles': consultorios_disponibles, 'hoy': hoy,
        'obras_sociales': obras_sociales,  
    })