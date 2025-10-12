from django.db import models
from django.contrib.auth.models import AbstractUser # Usaremos el sistema de Usuarios de Django para simplificar


# 1. Usuarios (Usaremos una extensión del modelo de Django para el rol)
class Usuario(AbstractUser):
    # Extensiones del modelo de usuario de Django
    ROL_CHOICES = [
        ('administrador', 'Administrador'),
        ('vendedor', 'Vendedor'),
        
    ]
    rol = models.CharField(max_length=15, choices=ROL_CHOICES, default='vendedor')
    # Los campos 'nombre', 'apellido', 'email', 'password', 'fecha_registro'
    # ya están cubiertos por AbstractUser.

    groups = models.ManyToManyField(
        'auth.Group',
        verbose_name=('groups'),
        blank=True,
        help_text=(
            'The groups this user belongs to. A user will get all permissions '
            'granted to each of their groups.'
        ),
        related_name="inventario_usuario_set",  # <-- related_name ÚNICO
        related_query_name="usuario",
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        verbose_name=('user permissions'),
        blank=True,
        help_text=('Specific permissions for this user.'),
        related_name="inventario_permisos_set", # <-- related_name ÚNICO
        related_query_name="usuario",
    )

    class Meta:
        verbose_name = "Usuario"
        verbose_name_plural = "Usuarios"

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.rol})"