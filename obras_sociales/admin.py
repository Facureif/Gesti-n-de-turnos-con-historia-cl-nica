from django.contrib import admin
from .models import ObraSocial, Plan


class PlanInline(admin.TabularInline):
    model = Plan
    extra = 1
    fields = ('nombre', 'requiere_autorizacion', 'coseguro_fijo', 
              'coseguro_porcentaje')


@admin.register(ObraSocial)
class ObraSocialAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'sigla', 'telefono', 'activo')
    list_filter = ('activo',)
    search_fields = ('nombre', 'sigla')
    ordering = ('nombre',)
    inlines = [PlanInline]
    
    fieldsets = (
        (None, {
            'fields': ('nombre', 'sigla', 'telefono', 'email')
        }),
        ('Estado', {
            'fields': ('activo',)
        }),
    )


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'obra_social', 'coseguro_fijo', 
                    'coseguro_porcentaje', 'requiere_autorizacion')
    list_filter = ('obra_social', 'requiere_autorizacion')
    search_fields = ('nombre', 'obra_social__nombre', 'obra_social__sigla')
    ordering = ('obra_social__nombre', 'nombre')