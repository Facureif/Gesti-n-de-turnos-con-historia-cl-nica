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
    """Vista para que el profesional vea y edite su perfil."""
    if request.user.rol != 'profesional':
        messages.error(request, 'No tenés acceso.')
        return redirect('home')
    
    profesional = get_object_or_404(Profesional, usuario=request.user)
    
    if request.method == 'POST':
        # Actualizar datos del usuario
        request.user.first_name = request.POST.get('nombre', request.user.first_name)
        request.user.last_name = request.POST.get('apellido', request.user.last_name)
        request.user.email = request.POST.get('email', request.user.email)
        request.user.telefono = request.POST.get('telefono', request.user.telefono)
        request.user.save()
        
        # Actualizar datos del profesional
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
        establecimientos_ids = request.POST.getlist('establecimientos')
        profesional.establecimientos.set(establecimientos_ids)
        
        # Foto de perfil
        if 'foto' in request.FILES:
            profesional.foto = request.FILES['foto']
        
        profesional.save()
        
        messages.success(request, 'Perfil actualizado correctamente.')
        return redirect('mi_perfil')
    
    return render(request, 'profesionales/perfil.html', {
    'profesional': profesional,
    'establecimientos_disponibles': Establecimiento.objects.filter(activo=True),
})

