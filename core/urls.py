from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core_app.urls')),
    path('usuarios/', include('usuarios.urls')), 
    path('profesionales/', include('profesionales.urls')), 
    path('turnos/', include('turnos.urls')),
    path('pacientes/', include('pacientes.urls')), 
    path('rapido/', include('turnos_rapidos.urls')),        
    path('profesional/', include('turnos_profesionales.urls')), 
    path('paciente/', include('pacientes.urls_portal')),


]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)