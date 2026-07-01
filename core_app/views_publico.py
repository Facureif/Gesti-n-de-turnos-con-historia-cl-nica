from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from establecimientos.models import Establecimiento
from profesionales.models import Profesional
from usuarios.models import Usuario
from datetime import date, timedelta, datetime
from turnos_profesionales.models import TurnoProfesional
from agendas.models import Agenda, HorarioAtencion


def portal_consultorio(request, nombre):
    """Portal público de un consultorio."""
    consultorio = get_object_or_404(Establecimiento, nombre__icontains=nombre.replace('-', ' '))
    profesionales = Profesional.objects.filter(establecimientos=consultorio, activo=True)
    
    return render(request, 'publico/portal_consultorio.html', {
        'consultorio': consultorio,
        'profesionales': profesionales
    })


def sacar_turno_consultorio(request, nombre, profesional_id):
    """Sacar turno en un consultorio específico."""
    consultorio = get_object_or_404(Establecimiento, nombre__icontains=nombre.replace('-', ' '))
    profesional = get_object_or_404(Profesional, id=profesional_id, establecimientos=consultorio, activo=True)
    
    # Acá va la lógica de sacar turno (similar a la del paciente)
    return render(request, 'publico/sacar_turno.html', {
        'consultorio': consultorio,
        'profesional': profesional
    })


def portal_profesional(request, username):
    """Portal público de un profesional independiente."""
    usuario = get_object_or_404(Usuario, username=username, rol='profesional')
    profesional = get_object_or_404(Profesional, usuario=usuario, activo=True)
    consultorios = profesional.establecimientos.all()
    
    return render(request, 'publico/portal_profesional.html', {
        'profesional': profesional,
        'consultorios': consultorios
    })


def sacar_turno_profesional(request, username):
    """Sacar turno con un profesional específico."""
    usuario = get_object_or_404(Usuario, username=username, rol='profesional')
    profesional = get_object_or_404(Profesional, usuario=usuario, activo=True)
    
    # El paciente elige consultorio primero
    return render(request, 'publico/sacar_turno.html', {
        'profesional': profesional,
        'consultorios': profesional.establecimientos.all()
    })


