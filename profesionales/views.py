from decimal import Decimal, InvalidOperation
from datetime import date, timedelta
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Profesional
from agendas.models import Agenda, HorarioAtencion
from establecimientos.models import Establecimiento
from obras_sociales.models import ObraSocial, Plan
from core_app.models import ClienteSaaS


@login_required
def mi_perfil(request):
    if request.user.rol != 'profesional':
        messages.error(request, 'No tenés acceso.')
        return redirect('home')

    profesional = get_object_or_404(Profesional, usuario=request.user)

    # Obtener cliente_slug de sesión
    cliente_slug = request.session.get('cliente_slug')
    cliente = None
    if cliente_slug:
        try:
            cliente = ClienteSaaS.objects.get(slug=cliente_slug, activo=True)
        except ClienteSaaS.DoesNotExist:
            cliente = None

    # ---------- Determinar consultorios editables ----------
    if cliente and cliente.tipo == 'consultorio':
        # Es un consultorio: solo el establecimiento del cliente
        establecimiento_cliente = cliente.establecimiento
        if establecimiento_cliente not in profesional.establecimientos.all():
            messages.error(request, 'No tenés permisos para este consultorio.')
            return redirect('panel_profesional')

        consultorios = [establecimiento_cliente]
        es_independiente = False
        cobertura_es_compartida = False
    else:
        # Profesional independiente: todos sus consultorios
        consultorios = list(profesional.establecimientos.all())
        if not consultorios:
            messages.error(request, 'No tenés consultorios asignados. Contactá al administrador.')
            return redirect('panel_profesional')

        es_independiente = True
        cobertura_es_compartida = True

    # ---------- POST ----------
    if request.method == 'POST':
        accion = request.POST.get('accion', '')

        # ========== DATOS PERSONALES ==========
        if accion == 'datos_personales':
            request.user.first_name = request.POST.get('nombre', request.user.first_name)
            request.user.last_name = request.POST.get('apellido', request.user.last_name)
            request.user.email = request.POST.get('email', request.user.email)
            request.user.telefono = request.POST.get('telefono', request.user.telefono)
            request.user.save()

            profesional.nombre = request.POST.get('nombre', profesional.nombre)
            profesional.apellido = request.POST.get('apellido', profesional.apellido)
            profesional.dni = request.POST.get('dni', profesional.dni)
            profesional.telefono = request.POST.get('telefono', profesional.telefono)
            profesional.email = request.POST.get('email', profesional.email)
            profesional.especialidad = request.POST.get('especialidad', profesional.especialidad)
            profesional.matricula = request.POST.get('matricula', profesional.matricula)
            profesional.descripcion = request.POST.get('descripcion', profesional.descripcion)
            profesional.color_calendario = request.POST.get('color_calendario', profesional.color_calendario)
            profesional.acepta_obra_social = request.POST.get('acepta_obra_social') == 'on'

            if 'foto' in request.FILES:
                profesional.foto = request.FILES['foto']

            profesional.save()
            messages.success(request, 'Perfil actualizado correctamente.')
            return redirect('mi_perfil')

        # ========== COBERTURA ==========
        if accion == 'guardar_cobertura':
            precio_str = request.POST.get('precio_particular', '').strip()
            obras_ids = request.POST.getlist('obras_sociales')
            planes_ids = request.POST.getlist('planes')
            tiene_plus = request.POST.get('tiene_plus') == 'on'
            texto_plus = request.POST.get('texto_plus', '').strip()

            obras = ObraSocial.objects.filter(id__in=obras_ids)
            planes_validos = Plan.objects.filter(id__in=planes_ids, obra_social__in=obras_ids)

            # Precio
            precio_val = None
            if precio_str:
                try:
                    precio_val = Decimal(precio_str)
                except InvalidOperation:
                    messages.error(request, 'Precio inválido.')
                    return redirect('mi_perfil')

            if es_independiente:
                # Guardar en profesional (aplica a todos los consultorios)
                if precio_val is not None:
                    profesional.precio_particular = precio_val
                profesional.obras_sociales.set(obras)
                profesional.planes.set(planes_validos)
                profesional.tiene_plus = tiene_plus
                profesional.texto_plus = texto_plus
                profesional.save()
            else:
                # Guardar en la agenda del consultorio del cliente
                agenda, _ = Agenda.objects.get_or_create(
                    profesional=profesional,
                    establecimiento=establecimiento_cliente,
                    defaults={
                        'fecha_inicio': date.today(),
                        'fecha_fin': date.today() + timedelta(days=365),
                        'pacientes_simultaneos': 1,
                        'acepta_sobreturnos': False,
                        'tiempo_entre_turnos': 0,
                    }
                )
                if precio_val is not None:
                    agenda.precio_particular = precio_val
                agenda.obras_sociales.set(obras)
                agenda.planes.set(planes_validos)
                agenda.tiene_plus = tiene_plus
                agenda.texto_plus = texto_plus
                agenda.save()

            messages.success(request, 'Cobertura actualizada correctamente.')
            return redirect('mi_perfil')

        # ========== HORARIOS DE UN CONSULTORIO ==========
        if accion == 'guardar_horarios':
            est_id = request.POST.get('establecimiento_id')
            try:
                est = Establecimiento.objects.get(id=est_id)
            except Establecimiento.DoesNotExist:
                messages.error(request, 'Consultorio no encontrado.')
                return redirect('mi_perfil')

            # Verificar pertenencia
            if est not in profesional.establecimientos.all():
                messages.error(request, 'No tenés permisos para este consultorio.')
                return redirect('mi_perfil')

            # Si es cliente consultorio, solo puede editar el suyo
            if cliente and cliente.tipo == 'consultorio' and est != cliente.establecimiento:
                messages.error(request, 'No podés editar este consultorio.')
                return redirect('mi_perfil')

            # Obtener o crear agenda
            agenda, _ = Agenda.objects.get_or_create(
                profesional=profesional,
                establecimiento=est,
                defaults={
                    'fecha_inicio': date.today(),
                    'fecha_fin': date.today() + timedelta(days=365),
                    'pacientes_simultaneos': 1,
                    'acepta_sobreturnos': False,
                    'tiempo_entre_turnos': 0,
                }
            )

            # Pacientes simultáneos
            sim = request.POST.get('pacientes_simultaneos', '').strip()
            if sim:
                try:
                    agenda.pacientes_simultaneos = max(1, int(sim))
                    agenda.save()
                except ValueError:
                    pass

            # Reemplazar horarios
            dias = request.POST.getlist('horario_dia')
            inicios = request.POST.getlist('horario_inicio')
            fines = request.POST.getlist('horario_fin')
            duraciones = request.POST.getlist('horario_duracion')

            agenda.horarios.all().delete()
            for dia, ini, fin, dur in zip(dias, inicios, fines, duraciones):
                if not (ini and fin and dur):
                    continue
                try:
                    HorarioAtencion.objects.create(
                        agenda=agenda,
                        dia=int(dia),
                        hora_inicio=ini,
                        hora_fin=fin,
                        duracion_turno=int(dur),
                    )
                except (ValueError, TypeError):
                    continue

            messages.success(request, f'Horarios de {est.nombre} actualizados.')
            return redirect('mi_perfil')

        return redirect('mi_perfil')

    # ---------- GET ----------
    # Armar lista de consultorios con su agenda y horarios
    consultorios_data = []
    for est in consultorios:
        agenda = Agenda.objects.filter(
            profesional=profesional,
            establecimiento=est
        ).first()
        consultorios_data.append({
            'establecimiento': est,
            'agenda': agenda,
            'horarios': list(agenda.horarios.all()) if agenda else [],
        })

    # Cobertura según tipo
    if es_independiente:
        precio_actual = profesional.precio_particular
        obras_ids_actuales = list(profesional.obras_sociales.values_list('id', flat=True))
        planes_ids_actuales = list(profesional.planes.values_list('id', flat=True))
        tiene_plus_actual = profesional.tiene_plus
        texto_plus_actual = profesional.texto_plus
    else:
        agenda_cliente = Agenda.objects.filter(
            profesional=profesional,
            establecimiento=establecimiento_cliente
        ).first()
        if agenda_cliente:
            precio_actual = agenda_cliente.precio_particular
            obras_ids_actuales = list(agenda_cliente.obras_sociales.values_list('id', flat=True))
            planes_ids_actuales = list(agenda_cliente.planes.values_list('id', flat=True))
            tiene_plus_actual = agenda_cliente.tiene_plus
            texto_plus_actual = agenda_cliente.texto_plus
        else:
            precio_actual = None
            obras_ids_actuales = []
            planes_ids_actuales = []
            tiene_plus_actual = False
            texto_plus_actual = ''

    obras_sociales_disponibles = ObraSocial.objects.filter(activo=True).prefetch_related('planes')

    return render(request, 'profesionales/perfil.html', {
        'profesional': profesional,
        'cliente': cliente,
        'es_independiente': es_independiente,
        'cobertura_es_compartida': cobertura_es_compartida,
        'consultorios_data': consultorios_data,
        'obras_sociales_disponibles': obras_sociales_disponibles,
        'precio_actual': precio_actual,
        'obras_ids_actuales': obras_ids_actuales,
        'planes_ids_actuales': planes_ids_actuales,
        'tiene_plus_actual': tiene_plus_actual,
        'texto_plus_actual': texto_plus_actual,
        'dias_semana': HorarioAtencion.DIAS,
    })