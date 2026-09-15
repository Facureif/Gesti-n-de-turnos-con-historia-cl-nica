# historias_clinicas/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q

from core_app.utils import get_cliente_actual
from profesionales.models import Profesional
from pacientes.models import Paciente
from pacientes.utils import tiene_acceso, puede_editar
from turnos_profesionales.views import _resolver_establecimiento
from agendas.models import Agenda
from .models import Ejercicio, ImagenEjercicio, PlanAlimentacion, ImagenPlanAlimentacion


def _obtener_paciente_validado(request, paciente_id):
    """
    Devuelve (paciente, profesional, establecimiento) o (None, None, None) si no tiene acceso.
    Usa la misma lógica que ficha_paciente.
    """
    if request.user.rol == 'secretaria':
        paciente = get_object_or_404(Paciente, id=paciente_id)
        return paciente, None, request.user.establecimiento

    # Profesional
    profesional = get_object_or_404(Profesional, usuario=request.user)
    paciente = get_object_or_404(Paciente, id=paciente_id)

    establecimiento = _resolver_establecimiento(request, profesional)

    # Si no vino por URL, priorizar el consultorio del paciente
    if not request.GET.get('establecimiento') and paciente.establecimiento_creacion:
        est_pac = paciente.establecimiento_creacion
        tiene_acceso_est = (
            est_pac in profesional.establecimientos.all() or
            Agenda.objects.filter(
                profesional=profesional, establecimiento=est_pac, activo=True
            ).exists()
        )
        if tiene_acceso_est:
            establecimiento = est_pac
            request.session['establecimiento_activo_id'] = est_pac.id

    if not establecimiento:
        messages.error(request, 'Seleccioná tu consultorio activo.')
        return None, None, None

    if not tiene_acceso(profesional, paciente, establecimiento):
        messages.error(request, 'No tenés acceso a este paciente.')
        return None, None, None

    return paciente, profesional, establecimiento


@login_required
def ejercicios_paciente(request, paciente_id):
    if request.user.rol not in ['profesional', 'secretaria']:
        return redirect('home')

    paciente, profesional, establecimiento = _obtener_paciente_validado(request, paciente_id)
    if paciente is None:
        return redirect('home')

    puede_ver_ejercicios = profesional.permite_ejercicios if profesional else True

    ejercicios = Ejercicio.objects.filter(paciente=paciente).order_by('-fecha')

    return render(request, 'historias_clinicas/ejercicios/lista.html', {
        'paciente': paciente,
        'ejercicios': ejercicios,
        'profesional': profesional,
        'puede_ver_ejercicios': puede_ver_ejercicios,
        'establecimiento_id': establecimiento.id if establecimiento else '',
    })


@login_required
def agregar_ejercicio(request, paciente_id):
    if request.user.rol not in ['profesional', 'secretaria']:
        return redirect('home')

    paciente, profesional, establecimiento = _obtener_paciente_validado(request, paciente_id)
    if paciente is None:
        return redirect('home')

    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        series = request.POST.get('series', 3)
        repeticiones = request.POST.get('repeticiones', 10)
        descripcion = request.POST.get('descripcion', '')
        link_video = request.POST.get('link_video', '')

        if not nombre:
            messages.error(request, 'El nombre del ejercicio es obligatorio.')
            return redirect('agregar_ejercicio', paciente_id=paciente.id)

        # Si es secretaria y no hay profesional, asignamos el profesional principal del cliente
        if not profesional:
            cliente = get_cliente_actual(request)
            if cliente and cliente.tipo == 'profesional':
                profesional = cliente.profesional
            elif cliente and cliente.tipo == 'consultorio' and cliente.establecimiento:
                primer_profesional = Profesional.objects.filter(
                    establecimientos=cliente.establecimiento, activo=True
                ).first()
                profesional = primer_profesional

        ejercicio = Ejercicio.objects.create(
            profesional=profesional,
            paciente=paciente,
            nombre=nombre,
            series=series,
            repeticiones=repeticiones,
            descripcion=descripcion,
            link_video=link_video,
        )

        imagenes = request.FILES.getlist('imagenes')
        for imagen in imagenes:
            ImagenEjercicio.objects.create(ejercicio=ejercicio, imagen=imagen)

        messages.success(request, 'Ejercicio agregado correctamente.')
        return redirect('ejercicios_paciente', paciente_id=paciente.id)

    return render(request, 'historias_clinicas/ejercicios/form.html', {
        'paciente': paciente,
        'profesional': profesional,
        'ejercicio': None,
        'establecimiento_id': establecimiento.id if establecimiento else '',
    })


@login_required
def editar_ejercicio(request, ejercicio_id):
    if request.user.rol not in ['profesional', 'secretaria']:
        return redirect('home')

    ejercicio = get_object_or_404(Ejercicio, id=ejercicio_id)
    paciente, profesional, establecimiento = _obtener_paciente_validado(request, ejercicio.paciente.id)
    if paciente is None:
        return redirect('home')

    if request.method == 'POST':
        ejercicio.nombre = request.POST.get('nombre', ejercicio.nombre)
        ejercicio.series = request.POST.get('series', ejercicio.series)
        ejercicio.repeticiones = request.POST.get('repeticiones', ejercicio.repeticiones)
        ejercicio.descripcion = request.POST.get('descripcion', ejercicio.descripcion)
        ejercicio.link_video = request.POST.get('link_video', ejercicio.link_video)
        ejercicio.save()

        imagenes = request.FILES.getlist('imagenes')
        if imagenes:
            for imagen in imagenes:
                ImagenEjercicio.objects.create(ejercicio=ejercicio, imagen=imagen)

        messages.success(request, 'Ejercicio actualizado.')
        return redirect('ejercicios_paciente', paciente_id=paciente.id)

    return render(request, 'historias_clinicas/ejercicios/form.html', {
        'paciente': paciente,
        'ejercicio': ejercicio,
        'profesional': profesional,
        'establecimiento_id': establecimiento.id if establecimiento else '',
    })


@login_required
def eliminar_ejercicio(request, ejercicio_id):
    if request.user.rol not in ['profesional', 'secretaria']:
        return redirect('home')

    ejercicio = get_object_or_404(Ejercicio, id=ejercicio_id)
    paciente, profesional, establecimiento = _obtener_paciente_validado(request, ejercicio.paciente.id)
    if paciente is None:
        return redirect('home')

    paciente_id = paciente.id
    ejercicio.delete()
    messages.success(request, 'Ejercicio eliminado.')
    return redirect('ejercicios_paciente', paciente_id=paciente_id)


@login_required
def eliminar_imagen_ejercicio(request, imagen_id):
    if request.user.rol not in ['profesional', 'secretaria']:
        return redirect('home')

    imagen = get_object_or_404(ImagenEjercicio, id=imagen_id)
    paciente, profesional, establecimiento = _obtener_paciente_validado(request, imagen.ejercicio.paciente.id)
    if paciente is None:
        return redirect('home')

    paciente_id = paciente.id
    imagen.delete()
    messages.success(request, 'Imagen eliminada.')
    return redirect('ejercicios_paciente', paciente_id=paciente_id)


@login_required
def planes_alimentacion_paciente(request, paciente_id):
    if request.user.rol not in ['profesional', 'secretaria']:
        return redirect('home')

    paciente, profesional, establecimiento = _obtener_paciente_validado(request, paciente_id)
    if paciente is None:
        return redirect('home')

    puede_ver_planes = profesional.permite_planes_alimentacion if profesional else True

    planes = PlanAlimentacion.objects.filter(paciente=paciente).order_by('-fecha')

    return render(request, 'historias_clinicas/planes/lista.html', {
        'paciente': paciente,
        'planes': planes,
        'profesional': profesional,
        'puede_ver_planes': puede_ver_planes,
        'establecimiento_id': establecimiento.id if establecimiento else '',
    })


@login_required
def agregar_plan_alimentacion(request, paciente_id):
    if request.user.rol not in ['profesional', 'secretaria']:
        return redirect('home')

    paciente, profesional, establecimiento = _obtener_paciente_validado(request, paciente_id)
    if paciente is None:
        return redirect('home')

    if request.method == 'POST':
        calorias = request.POST.get('calorias_objetivo')
        plan = PlanAlimentacion.objects.create(
            profesional=profesional,
            paciente=paciente,
            calorias_objetivo=calorias if calorias else None,
            desayuno=request.POST.get('desayuno', ''),
            almuerzo=request.POST.get('almuerzo', ''),
            merienda=request.POST.get('merienda', ''),
            cena=request.POST.get('cena', ''),
            observaciones=request.POST.get('observaciones', ''),
            link_video=request.POST.get('link_video', ''),
        )

        imagenes = request.FILES.getlist('imagenes')
        for img in imagenes:
            ImagenPlanAlimentacion.objects.create(plan=plan, imagen=img)

        messages.success(request, 'Plan de alimentación creado correctamente.')
        return redirect('planes_alimentacion_paciente', paciente_id=paciente.id)

    return render(request, 'historias_clinicas/planes/form.html', {
        'paciente': paciente,
        'profesional': profesional,
        'plan': None,
        'establecimiento_id': establecimiento.id if establecimiento else '',
    })


@login_required
def editar_plan_alimentacion(request, plan_id):
    if request.user.rol not in ['profesional', 'secretaria']:
        return redirect('home')

    plan = get_object_or_404(PlanAlimentacion, id=plan_id)
    paciente, profesional, establecimiento = _obtener_paciente_validado(request, plan.paciente.id)
    if paciente is None:
        return redirect('home')

    if request.method == 'POST':
        plan.calorias_objetivo = request.POST.get('calorias_objetivo') or None
        plan.desayuno = request.POST.get('desayuno', '')
        plan.almuerzo = request.POST.get('almuerzo', '')
        plan.merienda = request.POST.get('merienda', '')
        plan.cena = request.POST.get('cena', '')
        plan.observaciones = request.POST.get('observaciones', '')
        plan.link_video = request.POST.get('link_video', '')
        plan.save()

        imagenes = request.FILES.getlist('imagenes')
        if imagenes:
            for img in imagenes:
                ImagenPlanAlimentacion.objects.create(plan=plan, imagen=img)

        messages.success(request, 'Plan actualizado.')
        return redirect('planes_alimentacion_paciente', paciente_id=paciente.id)

    return render(request, 'historias_clinicas/planes/form.html', {
        'paciente': paciente,
        'plan': plan,
        'profesional': profesional,
        'establecimiento_id': establecimiento.id if establecimiento else '',
    })


@login_required
def eliminar_plan_alimentacion(request, plan_id):
    if request.user.rol not in ['profesional', 'secretaria']:
        return redirect('home')

    plan = get_object_or_404(PlanAlimentacion, id=plan_id)
    paciente, profesional, establecimiento = _obtener_paciente_validado(request, plan.paciente.id)
    if paciente is None:
        return redirect('home')

    paciente_id = paciente.id
    plan.delete()
    messages.success(request, 'Plan eliminado.')
    return redirect('planes_alimentacion_paciente', paciente_id=paciente_id)


@login_required
def eliminar_imagen_plan(request, imagen_id):
    if request.user.rol not in ['profesional', 'secretaria']:
        return redirect('home')

    imagen = get_object_or_404(ImagenPlanAlimentacion, id=imagen_id)
    paciente, profesional, establecimiento = _obtener_paciente_validado(request, imagen.plan.paciente.id)
    if paciente is None:
        return redirect('home')

    paciente_id = paciente.id
    imagen.delete()
    messages.success(request, 'Imagen eliminada.')
    return redirect('planes_alimentacion_paciente', paciente_id=paciente_id)