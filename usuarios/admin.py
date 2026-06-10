from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import Usuario


# Formulario personalizado para CREAR usuario
class UsuarioCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = Usuario
        fields = ('username', 'email', 'first_name', 'last_name', 'rol', 'telefono')


# Formulario personalizado para EDITAR usuario
class UsuarioChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = Usuario
        fields = ('username', 'email', 'first_name', 'last_name', 'rol', 'telefono', 'is_active', 'is_staff')


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    # Usar nuestros formularios personalizados
    add_form = UsuarioCreationForm
    form = UsuarioChangeForm
    
    # Columnas que se muestran en la lista
    list_display = ('username', 'email', 'first_name', 'last_name', 'rol', 'is_active', 'is_staff')
    list_filter = ('rol', 'is_active', 'is_staff')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    ordering = ('username',)
    
    # Campos que se muestran en el formulario de EDICIÓN
    fieldsets = (
        ('Información de Acceso', {
            'fields': ('username', 'password')
        }),
        ('Información Personal', {
            'fields': ('first_name', 'last_name', 'email', 'telefono')
        }),
        ('Rol y Permisos', {
            'fields': ('rol', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        ('Fechas', {
            'fields': ('last_login', 'date_joined')
        }),
        ('Consultorio', {
            'fields': ('establecimiento',)
        }),
    )
    
    # Campos que se muestran en el formulario de CREACIÓN
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'first_name', 'last_name', 'rol', 'telefono', 'password1', 'password2'),
        }),
    )    