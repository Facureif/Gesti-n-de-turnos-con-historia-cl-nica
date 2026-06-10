from django.contrib import admin
from .models import PlantillaMensaje, Recordatorio


@admin.register(PlantillaMensaje)
class PlantillaMensajeAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'tipo', 'profesional', 'activo')
    list_filter = ('tipo', 'profesional')
    search_fields = ('nombre', 'contenido')
    
    fieldsets = (
        (None, {
            'fields': ('nombre', 'tipo', 'profesional')
        }),
        ('Contenido', {
            'fields': ('contenido',),
            'description': 'Variables disponibles: {nombre}, {fecha}, {hora}, {profesional}'
        }),
    )


@admin.register(Recordatorio)
class RecordatorioAdmin(admin.ModelAdmin):
    list_display = ('turno', 'canal', 'momento_envio', 'enviado', 'confirmado')
    list_filter = ('canal', 'enviado', 'confirmado')
    date_hierarchy = 'momento_envio'
    readonly_fields = ('fecha_envio', 'respuesta')