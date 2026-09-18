from django.contrib.auth import logout
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from profesionales.models import Profesional
from .models import ClienteSaaS


def _profesional_pertenece_a_cliente(profesional, cliente):
    """Devuelve True si el profesional pertenece al cliente dado."""
    if cliente.tipo == 'consultorio':
        return cliente.establecimiento in profesional.establecimientos.all()
    elif cliente.tipo == 'profesional':
        return cliente.profesional_id == profesional.id
    return False


def home(request):
    if request.user.is_authenticated:
        if request.user.rol == 'profesional':
            return _home_profesional(request)
        elif request.user.rol == 'secretaria':
            return redirect('panel_secretaria')
        elif request.user.rol == 'paciente':
            return redirect('panel_paciente')
    return redirect('portal_cliente', cliente_slug='salta')


def _home_profesional(request):
    """
    Resuelve el home del profesional:
    - Si hay cliente en sesión y NO pertenece → logout + error
    - Si hay cliente en sesión y pertenece → panel
    - Sin cliente → buscar automáticamente o ir a selector
    """
    profesional = Profesional.objects.filter(usuario=request.user).first()
    if not profesional:
        messages.error(request, 'No tenés un perfil de profesional asociado.')
        logout(request)
        return redirect('login')

    cliente_slug = request.session.get('cliente_slug')

    # 1. Si hay cliente activo, verificar pertenencia
    if cliente_slug:
        try:
            cliente = ClienteSaaS.objects.get(slug=cliente_slug, activo=True)
            if not _profesional_pertenece_a_cliente(profesional, cliente):
                # NO pertenece → logout y error
                nombre_cliente = cliente.nombre
                logout(request)
                messages.error(
                    request,
                    f'Tu cuenta no está registrada en "{nombre_cliente}". '
                    f'Verificá el consultorio en el que intentás ingresar o '
                    f'contactá al administrador.'
                )
                return redirect('portal_cliente', cliente_slug=cliente_slug)
        except ClienteSaaS.DoesNotExist:
            request.session.pop('cliente_slug', None)

    # 2. Sin cliente → resolver automáticamente
    # 2.a. Si es independiente (tiene su propio ClienteSaaS)
    cliente_independiente = ClienteSaaS.objects.filter(
        tipo='profesional', profesional=profesional, activo=True
    ).first()
    if cliente_independiente:
        request.session['cliente_slug'] = cliente_independiente.slug
        return redirect('panel_profesional')

    # 2.b. Si tiene un solo establecimiento, tomar el cliente de ese
    establecimientos = list(profesional.establecimientos.filter(activo=True))
    if len(establecimientos) == 1:
        cliente = ClienteSaaS.objects.filter(
            tipo='consultorio', establecimiento=establecimientos[0], activo=True
        ).first()
        if cliente:
            request.session['cliente_slug'] = cliente.slug
            return redirect('panel_profesional')

    # 2.c. Tiene varios establecimientos → selector
    return redirect('seleccionar_consultorio')

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