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