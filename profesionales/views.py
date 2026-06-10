from django.utils import timezone
from datetime import date, timedelta
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
        
        # Foto de perfil
        if 'foto' in request.FILES:
            profesional.foto = request.FILES['foto']
        
        profesional.save()
        
        messages.success(request, 'Perfil actualizado correctamente.')
        return redirect('mi_perfil')
    
    return render(request, 'profesionales/perfil.html', {
        'profesional': profesional
    })

@login_required
def panel_profesional(request):
    # Verificar que el usuario sea profesional
    if request.user.rol != 'profesional':
        return redirect('home')
    
    try:
        profesional = Profesional.objects.get(usuario=request.user)
    except Profesional.DoesNotExist:
        return redirect('home')
    
    hoy = date.today()
    
    # Turnos de hoy
    turnos_hoy = Turno.objects.filter(
        profesional=profesional,
        fecha=hoy
    ).order_by('hora_inicio')
    
    # Turnos de mañana
    manana = hoy + timedelta(days=1)
    turnos_manana = Turno.objects.filter(
        profesional=profesional,
        fecha=manana
    ).order_by('hora_inicio')
    
    # Próximos turnos (próximos 7 días)
    proxima_semana = hoy + timedelta(days=7)
    proximos_turnos = Turno.objects.filter(
        profesional=profesional,
        fecha__range=[manana + timedelta(days=1), proxima_semana],
        estado__in=['pendiente', 'confirmado']
    ).order_by('fecha', 'hora_inicio')
    
    # Estadísticas rápidas
    total_hoy = turnos_hoy.count()
    confirmados_hoy = turnos_hoy.filter(estado='confirmado').count()
    pendientes_hoy = turnos_hoy.filter(estado='pendiente').count()
    completados_hoy = turnos_hoy.filter(estado='completado').count()
    
    contexto = {
        'profesional': profesional,
        'hoy': hoy,
        'turnos_hoy': turnos_hoy,
        'turnos_manana': turnos_manana,
        'proximos_turnos': proximos_turnos,
        'total_hoy': total_hoy,
        'confirmados_hoy': confirmados_hoy,
        'pendientes_hoy': pendientes_hoy,
        'completados_hoy': completados_hoy,
    }
    
    return render(request, 'profesionales/panel.html', contexto)