from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib import messages
from .models import Usuario
from pacientes.models import Paciente


def registro_paciente(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        password2 = request.POST.get('password2')
        email = request.POST.get('email')
        nombre = request.POST.get('nombre')
        apellido = request.POST.get('apellido')
        dni = request.POST.get('dni')
        telefono = request.POST.get('telefono')
        fecha_nacimiento = request.POST.get('fecha_nacimiento')
        
        # Validaciones básicas
        if password != password2:
            messages.error(request, 'Las contraseñas no coinciden')
            return render(request, 'usuarios/registro.html')
        
        if Usuario.objects.filter(username=username).exists():
            messages.error(request, 'El nombre de usuario ya existe')
            return render(request, 'usuarios/registro.html')
        
        # Crear usuario
        usuario = Usuario.objects.create_user(
            username=username,
            password=password,
            email=email,
            first_name=nombre,
            last_name=apellido,
            rol='paciente'
        )
        
        # Crear paciente asociado
        Paciente.objects.create(
            usuario=usuario,
            nombre=nombre,
            apellido=apellido,
            dni=dni,
            telefono=telefono,
            email=email,
            fecha_nacimiento=fecha_nacimiento
        )
        
        login(request, usuario)
        messages.success(request, '¡Registro exitoso! Bienvenido/a')
        return redirect('home')
    
    return render(request, 'usuarios/registro.html')