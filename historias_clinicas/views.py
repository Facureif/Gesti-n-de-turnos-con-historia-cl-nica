from .models import Ejercicio, ImagenEjercicio
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