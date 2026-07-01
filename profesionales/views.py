from django.utils import timezone
from datetime import date, timedelta
from establecimientos.models import Establecimiento
from turnos.models import Turno
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Profesional
from agendas.models import Agenda, HorarioAtencion


@login_required
def mi_perfil(request):
    if request.user.rol != 'profesional':
        messages.error(request, 'No tenés acceso.')
        return redirect('home')
    
    profesional = get_object_or_404(Profesional, usuario=request.user)
    
    if request.method == 'POST':
        accion = request.POST.get('accion', '')
        
        # ========== CRUD CONSULTORIOS ==========
        if accion == 'agregar_consultorio':
            nombre = request.POST.get('consultorio_nombre', '').strip()
            direccion = request.POST.get('consultorio_direccion', '').strip()
            telefono = request.POST.get('consultorio_telefono', '').strip()
            email = request.POST.get('consultorio_email', '').strip()
            
            if nombre:
                est = Establecimiento.objects.create(
                    nombre=nombre,
                    direccion=direccion,
                    telefono=telefono,
                    email=email,
                    activo=True
                )
                profesional.establecimientos.add(est)
                messages.success(request, f'Consultorio "{nombre}" agregado.')
            else:
                messages.error(request, 'El nombre del consultorio es obligatorio.')
        
        elif accion == 'editar_consultorio':
            est_id = request.POST.get('consultorio_id')
            nombre = request.POST.get('consultorio_nombre', '').strip()
            direccion = request.POST.get('consultorio_direccion', '').strip()
            telefono = request.POST.get('consultorio_telefono', '').strip()
            email = request.POST.get('consultorio_email', '').strip()
            
            if est_id and nombre:
                est = get_object_or_404(Establecimiento, id=est_id, profesionales=profesional)
                est.nombre = nombre
                est.direccion = direccion
                est.telefono = telefono
                est.email = email
                est.save()
                messages.success(request, f'Consultorio "{nombre}" actualizado.')
            else:
                messages.error(request, 'El nombre es obligatorio.')
        
        elif accion == 'eliminar_consultorio':
            est_id = request.POST.get('consultorio_id')
            if est_id:
                est = get_object_or_404(Establecimiento, id=est_id, profesionales=profesional)
                nombre = est.nombre
                profesional.establecimientos.remove(est)
                messages.success(request, f'Consultorio "{nombre}" eliminado de tu perfil.')
        
        # ========== OBRAS SOCIALES Y PLANES ==========
        elif accion == 'guardar_obras_sociales':
            obras_sociales_ids = request.POST.getlist('obras_sociales')
            planes_ids = request.POST.getlist('planes')
            
            from obras_sociales.models import ObraSocial, Plan
            obras = ObraSocial.objects.filter(id__in=obras_sociales_ids)
            profesional.obras_sociales.set(obras)
            
            planes = Plan.objects.filter(id__in=planes_ids)
            profesional.planes.set(planes)
            
            messages.success(request, 'Obras sociales actualizadas.')
        
        # ========== DATOS PERSONALES ==========
        else:
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
    
    from obras_sociales.models import ObraSocial
    return render(request, 'profesionales/perfil.html', {
        'profesional': profesional,
        'mis_consultorios': profesional.establecimientos.all(),
        'obras_sociales_disponibles': ObraSocial.objects.filter(activo=True).prefetch_related('planes'),
    })