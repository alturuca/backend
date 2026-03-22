# inventario/views.py

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.contrib.auth import authenticate
from rest_framework import viewsets, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework_simplejwt.tokens import RefreshToken
from .models import Usuario, Producto, Factura, IngresoProducto, DetalleFactura
from .serializers import UsuarioSerializer, ProductoSerializer, FacturaSerializer, IngresoProductoSerializer
import json
from django.db.models import Sum, F
from django.utils import timezone


"""
Esta es la vista de usuarios
"""
# Vista de login que genera tokens JWT válidos
@method_decorator(csrf_exempt, name='dispatch')
class LoginView(APIView):
    def post(self, request, *args, **kwargs):
        data = request.data
        username = data.get('username')
        password = data.get('password')

        user = authenticate(request, username=username, password=password)
        if user is not None:
            refresh = RefreshToken.for_user(user)
            access_token = str(refresh.access_token)
            refresh_token = str(refresh)

            return JsonResponse({
                'message': 'Inicio de sesión exitoso',
                'username': user.username,
                'rol': getattr(user, 'rol', 'vendedor'),
                'access_token': str(refresh.access_token),
                'refresh_token': str(refresh)
            })
        else:
            return JsonResponse({'error': 'Credenciales inválidas'}, status=401)

# Vista protegida que devuelve los datos del usuario autenticado
class UserDataView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        return Response({
            'username': user.username,
            'first_name': user.first_name,
            'rol': getattr(user, 'rol', 'vendedor'),
        })

# Permisos personalizados: solo administradores pueden modificar
class SoloAdminPuedeModificar(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return request.user and request.user.is_authenticated
        return request.user and request.user.is_authenticated and request.user.is_staff

# ViewSet para usuarios
class UsuarioViewSet(viewsets.ModelViewSet):
    queryset = Usuario.objects.all()
    serializer_class = UsuarioSerializer
    permission_classes = [SoloAdminPuedeModificar]


"""
Esta es la vista de producto
"""
class ProductoViewSet(viewsets.ModelViewSet):
    queryset = Producto.objects.all()
    serializer_class = ProductoSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'sku'


"""
Esta es la vista de venta
"""

class FacturaViewSet(viewsets.ModelViewSet):
    queryset = Factura.objects.all()
    serializer_class = FacturaSerializer
    permission_classes = [IsAuthenticated]

"""
Esta es la vista de venta ingreso de producto
"""

class IngresoProductoViewSet(viewsets.ModelViewSet):
    queryset = IngresoProducto.objects.all()
    serializer_class = IngresoProductoSerializer
    permission_classes = [IsAuthenticated]


class ReporteVentasView(APIView):
    """
    Endpoint para obtener reportes de ventas.
    Permite filtrar por rango de fechas mediante parámetros en la URL.
    Ejemplo: /api/v1/reporte-ventas/?fecha_inicio=2026-03-01&fecha_fin=2026-03-21
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        # 1. Obtener parámetros de filtrado por fechas
        fecha_inicio = request.query_params.get('fecha_inicio')
        fecha_fin = request.query_params.get('fecha_fin')

        # Variables para la respuesta
        hoy = timezone.localdate()
        mes_actual = hoy.month
        anio_actual = hoy.year
        
        datos_respuesta = {
            "moneda": "COP"
        }

        # 2. Lógica de filtrado por RANGO (si existen fechas en la URL)
        if fecha_inicio and fecha_fin:
            ventas_rango = (
                DetalleFactura.objects
                .filter(factura__fecha__range=[fecha_inicio, fecha_fin])
                .aggregate(total=Sum(F('cantidad') * F('precio_unitario')))
                .get('total') or 0
            )
            datos_respuesta["total_rango"] = float(ventas_rango)
            datos_respuesta["periodo"] = f"{fecha_inicio} a {fecha_fin}"

        # 3. Lógica por DEFECTO (Ventas del día y del mes)
        ventas_dia = (
            DetalleFactura.objects
            .filter(factura__fecha=hoy)
            .aggregate(total=Sum(F('cantidad') * F('precio_unitario')))
            .get('total') or 0
        )

        ventas_mes = (
            DetalleFactura.objects
            .filter(
                factura__fecha__year=anio_actual,
                factura__fecha__month=mes_actual
            )
            .aggregate(total=Sum(F('cantidad') * F('precio_unitario')))
            .get('total') or 0
        )

        # Añadimos los datos estándar a la respuesta
        datos_respuesta["ventas_dia"] = float(ventas_dia)
        datos_respuesta["ventas_mes"] = float(ventas_mes)

        return Response(datos_respuesta)