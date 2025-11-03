from django.db import models
from django.contrib.auth.models import AbstractUser # Usaremos el sistema de Usuarios de Django para simplificar

"""
Esta es el area del usuario
"""
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
    

"""
Esta es el area de producto
"""

class Producto(models.Model):
    sku = models.CharField(max_length=30, unique=True)  # Código único del producto
    nombre = models.CharField(max_length=100)
    precio_compra = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    precio_venta = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    descripcion = models.TextField(blank=True)
    stock = models.PositiveIntegerField()
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.nombre} (SKU: {self.sku})"


"""
Modelo de la venta
"""

class Factura(models.Model):
    numero = models.AutoField(primary_key=True)  # identificador único
    cliente = models.CharField(max_length=100)
    fecha = models.DateField(auto_now_add=True)

    def total(self):
        return sum(item.subtotal() for item in self.detalles.all())

    def __str__(self):
        return f"Factura #{self.numero} - {self.cliente}"

class DetalleFactura(models.Model):
    factura = models.ForeignKey(Factura, related_name='detalles', on_delete=models.CASCADE)
    producto = models.CharField(max_length=100)
    cantidad = models.PositiveIntegerField()
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)

    def subtotal(self):
        return self.cantidad * self.precio_unitario

    def __str__(self):
        return f"{self.producto} x {self.cantidad}"

"""
Modelo de la compra de producto
"""

class IngresoProducto(models.Model):
    fecha = models.DateTimeField(auto_now_add=True)
    proveedor = models.CharField(max_length=100)

class DetalleIngresoProducto(models.Model):
    ingreso = models.ForeignKey(IngresoProducto, related_name='detalles', on_delete=models.CASCADE)
    producto = models.ForeignKey(Producto, to_field='sku', on_delete=models.CASCADE)
    cantidad = models.PositiveIntegerField()
    precio_compra = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    precio_venta = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    
    
    