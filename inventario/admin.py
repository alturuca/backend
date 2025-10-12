# inventario/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Usuario

# Personalizamos cómo se muestra el modelo Usuario en el admin
class UsuarioAdmin(UserAdmin):
    # Campos que se muestran en la lista de usuarios
    list_display = ('username', 'email', 'first_name', 'last_name', 'rol', 'is_staff')
    
    # Campos que se pueden editar al crear/modificar un usuario
    fieldsets = UserAdmin.fieldsets + (
        (None, {'fields': ('rol',)}), # Añadimos el campo 'rol' al final
    )
    
    # Campos que se pueden usar para filtrar en el panel lateral
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'rol')

# Registra tu modelo de Usuario con la configuración personalizada
admin.site.register(Usuario, UsuarioAdmin)