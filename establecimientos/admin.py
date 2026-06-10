from django.contrib import admin
from .models import Establecimiento, Sucursal


class SucursalInline(admin.TabularInline):
    model = Sucursal
    extra = 1


@admin.register(Establecimiento)
class EstablecimientoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'cuit', 'telefono', 'email', 'activo')
    search_fields = ('nombre', 'cuit')
    inlines = [SucursalInline]


@admin.register(Sucursal)
class SucursalAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'establecimiento', 'direccion', 'telefono')
    list_filter = ('establecimiento',)
    search_fields = ('nombre', 'direccion')