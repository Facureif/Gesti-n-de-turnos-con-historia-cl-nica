from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.decorators import login_required

from profesionales.models import Profesional
from .models import ClienteSaaS

def home(request):
    if request.user.is_authenticated:
        if request.user.rol == 'profesional':
            return redirect('panel_profesional')
        elif request.user.rol == 'secretaria':
            return redirect('panel_secretaria')
        elif request.user.rol == 'paciente':
            return redirect('panel_paciente')
    return redirect('portal_cliente', cliente_slug='salta')  # O al que quieras por defecto


# core_app/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from profesionales.models import Profesional
from core_app.models import ClienteSaaS


@login_required
def seleccionar_consultorio(request):
    if request.user.rol != 'profesional':
        return redirect('home')

    profesional = get_object_or_404(Profesional, usuario=request.user)
    establecimientos = profesional.establecimientos.filter(activo=True)

    if request.method == 'POST':
        slug = request.POST.get('cliente_slug')
        cliente = ClienteSaaS.objects.filter(
            slug=slug,
            activo=True,
            establecimiento__in=establecimientos
        ).first()

        if cliente:
            request.session['cliente_slug'] = cliente.slug
            return redirect('panel_profesional')

        messages.error(request, 'Consultorio inválido.')

    return render(request, 'core_app/seleccionar_consultorio.html', {
        'establecimientos': establecimientos,
    })