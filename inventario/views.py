# inventario/views.py

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.contrib.auth import authenticate
from rest_framework import viewsets, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from .models import Usuario, Producto, Factura, IngresoProducto
from .serializers import UsuarioSerializer, ProductoSerializer, FacturaSerializer, IngresoProductoSerializer
import json

"""
Esta es la vista de usuarios
"""
# Vista de login que genera tokens JWT válidos
@method_decorator(csrf_exempt, name='dispatch')
class LoginView(APIView):
    def post(self, request, *args, **kwargs):
        data = json.loads(request.body)
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
                'rol': user.rol,
                'access_token': access_token,
                'refresh_token': refresh_token
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