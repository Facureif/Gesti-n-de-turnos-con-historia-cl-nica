from .models import Ejercicio, ImagenEjercicio, PlanAlimentacion, ImagenPlanAlimentacion
from profesionales.models import Profesional
from pacientes.models import Paciente
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages



@login_required
def ejercicios_paciente(request, paciente_id):
    """Lista los ejercicios asignados a un paciente (vista profesional)."""
    if request.user.rol not in ['profesional', 'secretaria']:
        return redirect('home')
    paciente = get_object_or_404(Paciente, id=paciente_id)
    if request.user.rol == 'profesional':
        profesional = get_object_or_404(Profesional, usuario=request.user)
    else:
        profesional = None

    # Solo la secretaria puede ver ejercicios de todos (por ahora)
    puede_ver_ejercicios = profesional.permite_ejercicios if profesional else True

    ejercicios = Ejercicio.objects.filter(paciente=paciente).order_by('-fecha')

    return render(request, 'historias_clinicas/ejercicios/lista.html', {
        'paciente': paciente,
        'ejercicios': ejercicios,
        'profesional': profesional,
        'puede_ver_ejercicios': puede_ver_ejercicios,   # ← pasamos al template
    })

@login_required
def agregar_ejercicio(request, paciente_id):
    if request.user.rol not in ['profesional', 'secretaria']:
        return redirect('home')
    paciente = get_object_or_404(Paciente, id=paciente_id)
    if request.user.rol == 'profesional':
        profesional = get_object_or_404(Profesional, usuario=request.user)
    else:
        profesional = None

    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        series = request.POST.get('series', 3)
        repeticiones = request.POST.get('repeticiones', 10)
        descripcion = request.POST.get('descripcion', '')
        link_video = request.POST.get('link_video', '')

        if not nombre:
            messages.error(request, 'El nombre del ejercicio es obligatorio.')
            return redirect('agregar_ejercicio', paciente_id=paciente.id)

        # Crear el ejercicio UNA sola vez
        ejercicio = Ejercicio.objects.create(
            profesional=profesional if profesional else Profesional.objects.first(),  # fallback
            paciente=paciente,
            nombre=nombre,
            series=series,
            repeticiones=repeticiones,
            descripcion=descripcion,
            link_video=link_video,
        )

        # Guardar imágenes
        imagenes = request.FILES.getlist('imagenes')
        for imagen in imagenes:
            ImagenEjercicio.objects.create(ejercicio=ejercicio, imagen=imagen)

        messages.success(request, 'Ejercicio agregado correctamente.')
        return redirect('ejercicios_paciente', paciente_id=paciente.id)

    # GET
    return render(request, 'historias_clinicas/ejercicios/form.html', {
        'paciente': paciente,
        'profesional': profesional,
        'ejercicio': None,
    })


@login_required
def editar_ejercicio(request, ejercicio_id):
    if request.user.rol not in ['profesional', 'secretaria']:
        return redirect('home')
    ejercicio = get_object_or_404(Ejercicio, id=ejercicio_id)
    paciente = ejercicio.paciente
    if request.method == 'POST':
        ejercicio.nombre = request.POST.get('nombre', ejercicio.nombre)
        ejercicio.series = request.POST.get('series', ejercicio.series)
        ejercicio.repeticiones = request.POST.get('repeticiones', ejercicio.repeticiones)
        ejercicio.descripcion = request.POST.get('descripcion', ejercicio.descripcion)
        ejercicio.link_video = request.POST.get('link_video', ejercicio.link_video)
        ejercicio.save()
        messages.success(request, 'Ejercicio actualizado.')
        imagenes = request.FILES.getlist('imagenes')
        if imagenes:
            for imagen in imagenes:
                ImagenEjercicio.objects.create(ejercicio=ejercicio, imagen=imagen)

        return redirect('ejercicios_paciente', paciente_id=paciente.id)
    return render(request, 'historias_clinicas/ejercicios/form.html', {
        'paciente': paciente,
        'ejercicio': ejercicio,
    })

@login_required
def eliminar_ejercicio(request, ejercicio_id):
    if request.user.rol not in ['profesional', 'secretaria']:
        return redirect('home')
    ejercicio = get_object_or_404(Ejercicio, id=ejercicio_id)
    paciente_id = ejercicio.paciente.id
    ejercicio.delete()
    messages.success(request, 'Ejercicio eliminado.')
    return redirect('ejercicios_paciente', paciente_id=paciente_id)


@login_required
def eliminar_imagen_ejercicio(request, imagen_id):
    if request.user.rol not in ['profesional', 'secretaria']:
        return redirect('home')
    imagen = get_object_or_404(ImagenEjercicio, id=imagen_id)
    ejercicio_id = imagen.ejercicio.id
    imagen.delete()
    messages.success(request, 'Imagen eliminada.')
    return redirect('ejercicios_paciente', paciente_id=imagen.ejercicio.paciente.id)


@login_required
def planes_alimentacion_paciente(request, paciente_id):
    if request.user.rol not in ['profesional', 'secretaria']:
        return redirect('home')
    paciente = get_object_or_404(Paciente, id=paciente_id)
    if request.user.rol == 'profesional':
        profesional = get_object_or_404(Profesional, usuario=request.user)
    else:
        profesional = None

    puede_ver_planes = profesional.permite_planes_alimentacion if profesional else True

    planes = PlanAlimentacion.objects.filter(paciente=paciente).order_by('-fecha')
    return render(request, 'historias_clinicas/planes/lista.html', {
        'paciente': paciente,
        'planes': planes,
        'profesional': profesional,
        'puede_ver_planes': puede_ver_planes,
    })


@login_required
def agregar_plan_alimentacion(request, paciente_id):
    if request.user.rol not in ['profesional', 'secretaria']:
        return redirect('home')
    paciente = get_object_or_404(Paciente, id=paciente_id)
    if request.user.rol == 'profesional':
        profesional = get_object_or_404(Profesional, usuario=request.user)
    else:
        profesional = None

    if request.method == 'POST':
        calorias = request.POST.get('calorias_objetivo')
        plan = PlanAlimentacion.objects.create(
            profesional=profesional if profesional else Profesional.objects.first(),
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
    })


@login_required
def editar_plan_alimentacion(request, plan_id):
    if request.user.rol not in ['profesional', 'secretaria']:
        return redirect('home')
    plan = get_object_or_404(PlanAlimentacion, id=plan_id)
    paciente = plan.paciente

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
        'profesional': getattr(plan, 'profesional', None),
    })


@login_required
def eliminar_plan_alimentacion(request, plan_id):
    if request.user.rol not in ['profesional', 'secretaria']:
        return redirect('home')
    plan = get_object_or_404(PlanAlimentacion, id=plan_id)
    paciente_id = plan.paciente.id
    plan.delete()
    messages.success(request, 'Plan eliminado.')
    return redirect('planes_alimentacion_paciente', paciente_id=paciente_id)


@login_required
def eliminar_imagen_plan(request, imagen_id):
    if request.user.rol not in ['profesional', 'secretaria']:
        return redirect('home')
    imagen = get_object_or_404(ImagenPlanAlimentacion, id=imagen_id)
    plan_id = imagen.plan.id
    paciente_id = imagen.plan.paciente.id
    imagen.delete()
    messages.success(request, 'Imagen eliminada.')
    return redirect('planes_alimentacion_paciente', paciente_id=paciente_id)