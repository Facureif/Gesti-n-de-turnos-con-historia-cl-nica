from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required

def home(request):
    # Si el usuario está logueado y es profesional, redirigir al panel
    # if request.user.is_authenticated:
    #     if request.user.rol == 'profesional':
    #         return redirect('panel_profesional')
    
    return render(request, 'core_app/home.html')


# def home(request):
#     if request.user.is_authenticated:
#         if request.user.rol == 'profesional':
#             # Por ahora redirigimos al panel rápido
#             # Después podemos hacer que dependa del tipo de plan contratado
#             return redirect('panel_rapido')
#     return render(request, 'core_app/home.html')