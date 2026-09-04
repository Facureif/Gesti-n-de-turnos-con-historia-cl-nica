from decimal import Decimal, InvalidOperation
from datetime import date, timedelta
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Profesional
from agendas.models import Agenda
from establecimientos.models import Establecimiento
from obras_sociales.models import ObraSocial, Plan
from core_app.models import ClienteSaaS  # Asegurate de importar tu modelo

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

    # Determinar establecimiento (consultorio) actual
    if cliente and cliente.tipo == 'consultorio':
        # El cliente es un consultorio, usar su establecimiento
        establecimiento_actual = cliente.establecimiento
        # Verificar que el profesional pertenezca a ese establecimiento
        if establecimiento_actual not in profesional.establecimientos.all():
            messages.error(request, 'No tenés permisos para este consultorio.')
            return redirect('panel_profesional')
    else:
        # Si no hay cliente o es profesional independiente, usar el primer establecimiento del profesional
        establecimiento_actual = profesional.establecimientos.first()
        if not establecimiento_actual:
            messages.error(request, 'No tenés consultorios asignados.')
            return redirect('panel_profesional')

    # Obtener agenda del establecimiento actual
    agenda_actual = Agenda.objects.filter(
        profesional=profesional,
        establecimiento=establecimiento_actual
    ).first()

    if request.method == 'POST':
        accion = request.POST.get('accion', '')

        # ========== GUARDAR CONSULTORIO ==========
        if accion == 'guardar_consultorio_completo':
            # Actualizar datos del establecimiento
            nombre = request.POST.get('consultorio_nombre', '').strip()
            direccion = request.POST.get('consultorio_direccion', '').strip()
            telefono = request.POST.get('consultorio_telefono', '').strip()
            email = request.POST.get('consultorio_email', '').strip()
            if nombre:
                establecimiento_actual.nombre = nombre
            establecimiento_actual.direccion = direccion
            establecimiento_actual.telefono = telefono
            establecimiento_actual.email = email
            establecimiento_actual.save()

            # Obtener o crear agenda
            agenda = Agenda.objects.filter(
                profesional=profesional,
                establecimiento=establecimiento_actual
            ).first()
            if not agenda:
                agenda = Agenda.objects.create(
                    profesional=profesional,
                    establecimiento=establecimiento_actual,
                    fecha_inicio=date.today(),
                    fecha_fin=date.today() + timedelta(days=365),
                    pacientes_simultaneos=1,
                    acepta_sobreturnos=False,
                    tiempo_entre_turnos=0,
                )

            # Precio particular (si se ingresa, se actualiza; si se deja vacío, se mantiene el anterior)
            precio_str = request.POST.get('precio_consultorio', '').strip()
            if precio_str:
                try:
                    agenda.precio_particular = Decimal(precio_str)
                except InvalidOperation:
                    messages.error(request, 'Precio inválido.')
                    return redirect('mi_perfil')
            # Si está vacío, no se modifica (conserva el valor actual)

            # Contacto (solo actualizar si se proporciona un valor)
            email_contacto = request.POST.get('email_contacto', '').strip()
            telefono_contacto = request.POST.get('telefono_contacto', '').strip()
            if email_contacto:
                agenda.email_contacto = email_contacto
            if telefono_contacto:
                agenda.telefono_contacto = telefono_contacto

            agenda.save()

            # Obras sociales y planes
            obras_ids = request.POST.getlist('obras_sociales_consultorio')
            obras = ObraSocial.objects.filter(id__in=obras_ids)
            agenda.obras_sociales.set(obras)

            planes_ids = request.POST.getlist('planes_consultorio')
            # Filtrar planes que pertenezcan a las OS seleccionadas
            planes_validos = Plan.objects.filter(
                id__in=planes_ids,
                obra_social__in=obras_ids
            )
            agenda.planes.set(planes_validos)

            messages.success(request, 'Consultorio actualizado correctamente.')
            return redirect('mi_perfil')

        # ========== DATOS PERSONALES ==========
        elif accion == 'datos_personales':
            # Actualizar usuario
            request.user.first_name = request.POST.get('nombre', request.user.first_name)
            request.user.last_name = request.POST.get('apellido', request.user.last_name)
            request.user.email = request.POST.get('email', request.user.email)
            request.user.telefono = request.POST.get('telefono', request.user.telefono)
            request.user.save()

            # Actualizar profesional
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

        # Otras acciones (agregar/eliminar consultorio, cambiar, etc.) no son necesarias con este enfoque

        return redirect('mi_perfil')

    # ========== GET ==========
    # Inicializar atributos para el template
    establecimiento_actual.precio_agenda = None
    establecimiento_actual.email_contacto_agenda = None
    establecimiento_actual.telefono_contacto_agenda = None
    establecimiento_actual.obras_sociales_agenda_ids = []
    establecimiento_actual.planes_agenda_ids = []

    if agenda_actual:
        establecimiento_actual.precio_agenda = agenda_actual.precio_particular
        establecimiento_actual.email_contacto_agenda = agenda_actual.email_contacto
        establecimiento_actual.telefono_contacto_agenda = agenda_actual.telefono_contacto
        establecimiento_actual.obras_sociales_agenda_ids = list(
            agenda_actual.obras_sociales.values_list('id', flat=True)
        )
        # Filtrar planes solo de las obras sociales seleccionadas
        establecimiento_actual.planes_agenda_ids = list(
            agenda_actual.planes.filter(
                obra_social__in=establecimiento_actual.obras_sociales_agenda_ids
            ).values_list('id', flat=True)
        )

    obras_sociales_disponibles = ObraSocial.objects.filter(activo=True).prefetch_related('planes')

    return render(request, 'profesionales/perfil.html', {
        'profesional': profesional,
        'consultorio_actual': establecimiento_actual,
        'obras_sociales_disponibles': obras_sociales_disponibles,
        'agenda_actual': agenda_actual,
    })