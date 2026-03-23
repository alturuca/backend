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
from django.db.models import Sum, F, Count
from django.utils import timezone
from django.db.models.functions import TruncDay, TruncWeek
from datetime import timedelta
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
    permission_classes = [IsAdminUser]

    def get(self, request):
        hoy = timezone.localdate()
        # Calculamos 4 semanas atrás (28 días)
        hace_28_dias = hoy - timedelta(days=27)
        
        # 1. OBTENER DATOS AGRUPADOS POR SEMANA
        reporte_por_semanas = (
            DetalleFactura.objects
            .filter(factura__fecha__range=[hace_28_dias, hoy])
            .annotate(semana=TruncWeek('factura__fecha'))
            .values('semana')
            .annotate(
                total_ventas=Sum(F('cantidad') * F('precio_unitario')),
                num_facturas=Count('factura', distinct=True)
            )
            .order_by('semana')
        )

        # 2. FORMATEAR CON NOMBRES ESPECÍFICOS
        registros = list(reporte_por_semanas)
        tendencia_semanal = []
        # Nombres que queremos mostrar en el frontend
        nombres_labels = ["Sem 1", "Sem 2", "Semana Pasada", "Esta Semana"]
        
        # Llenamos las 4 posiciones (de la más antigua a la más reciente)
        for i in range(4):
            # Buscamos el registro correspondiente en la lista (de atrás hacia adelante)
            # El índice -1 es "Esta Semana", -2 es "Semana Pasada", etc.
            idx_busqueda = len(registros) - (4 - i)
            
            nombre_final = nombres_labels[i]
            
            if idx_busqueda >= 0:
                item = registros[idx_busqueda]
                ventas = float(item['total_ventas'] or 0)
                facturas = item['num_facturas'] or 0
                
                tendencia_semanal.append({
                    "nombre": nombre_final,
                    "ventas": ventas,
                    "ticket_promedio": ventas / facturas if facturas > 0 else 0
                })
            else:
                # Si no hay ventas registradas para esa semana, enviamos 0
                tendencia_semanal.append({
                    "nombre": nombre_final,
                    "ventas": 0,
                    "ticket_promedio": 0
                })

        # 3. TOTALES GENERALES
        # (Se mantiene igual para no romper tus tarjetas de arriba)
        ventas_mes_data = DetalleFactura.objects.filter(
            factura__fecha__year=hoy.year,
            factura__fecha__month=hoy.month
        ).aggregate(
            total=Sum(F('cantidad') * F('precio_unitario')),
            facturas=Count('factura', distinct=True)
        )

        total_ventas_mes = float(ventas_mes_data['total'] or 0)
        total_facturas_mes = ventas_mes_data['facturas'] or 0

        ventas_dia = DetalleFactura.objects.filter(
            factura__fecha=hoy
        ).aggregate(total=Sum(F('cantidad') * F('precio_unitario')))['total'] or 0

        return Response({
            "moneda": "COP",
            "ventas_dia": float(ventas_dia),
            "ventas_mes": total_ventas_mes,
            "utilidad_mes": total_ventas_mes * 0.40,
            "ticket_promedio_mes": total_ventas_mes / total_facturas_mes if total_facturas_mes > 0 else 0,
            "conteo_facturas_mes": total_facturas_mes,
            "tendencia_semanal": tendencia_semanal
        })
    
class DashboardStatsView(APIView):
    
    permission_classes = [IsAuthenticated]

    def get(self, request):
        hoy = timezone.localdate()
        
        # 1. Ventas del Día (ID: 1)
        # Sumamos el subtotal (cantidad * precio) de todos los detalles de facturas de hoy
        ventas_dia = (
            DetalleFactura.objects
            .filter(factura__fecha=hoy)
            .aggregate(total=Sum(F('cantidad') * F('precio_unitario')))
            .get('total') or 0
        )
        
        # 2. Productos en Stock (ID: 2)
        # Sumamos la columna 'stock' de todos los productos en la base de datos
        total_stock = Producto.objects.aggregate(total=Sum('stock'))['total'] or 0
        
        # 4. Bajo Stock (ID: 4)
        # Contamos cuántos productos tienen menos de 10 unidades
        conteo_bajo_stock = Producto.objects.filter(stock__lt=10).count()

        # Formateamos la respuesta para que React la reciba exactamente como la necesita
        data = [
            { 
                "id": 1, 
                "name": 'Ventas del Día', 
                "value": f"${float(ventas_dia):,.0f}", # Formato $1.240.000
                "change": 'Hoy', 
                "changeType": 'increase' 
            },
            { 
                "id": 2, 
                "name": 'Productos en Stock', 
                "value": str(total_stock), 
                "change": 'Total items', 
                "changeType": 'neutral' 
            },
            { 
                "id": 3, 
                "name": 'Bajo Stock', 
                "value": str(conteo_bajo_stock), 
                "change": 'Revisar', 
                "changeType": 'decrease' 
            },
        ]
        
        return Response(data)

class ReporteUtilidadView(APIView):
    def get(self, request):
        hoy = timezone.localdate()
        inicio_mes = hoy.replace(day=1)
        inicio_semana = hoy - timedelta(days=hoy.weekday()) 

        def calcular_datos(queryset):
            # 1. Agregamos el total de dinero y el conteo de facturas únicas
            # Usamos distinct=True porque un DetalleFactura pertenece a una Factura;
            # si una factura tiene 3 productos, Count('factura') daría 3, pero distinct=True da 1.
            resultado = queryset.aggregate(
                total_ventas=Sum(F('cantidad') * F('precio_unitario')),
                total_facturas=Count('factura', distinct=True)
            )
            
            ventas = resultado['total_ventas'] or 0
            num_facturas = resultado['total_facturas'] or 0
            
            # 2. Cálculo del Ticket Promedio
            # Evitamos el error de división por cero si no hay ventas aún
            ticket_promedio = ventas / num_facturas if num_facturas > 0 else 0
            
            return {
                "ventas": float(ventas),
                "utilidad": float(ventas) * 0.40,
                "ticket_promedio": float(ticket_promedio), # ✅ Dato real
                "conteo_facturas": num_facturas           # ✅ Útil para auditoría
            }

        # Consultas filtradas (ya corregidas para DateField)
        datos_diarios = DetalleFactura.objects.filter(factura__fecha=hoy)
        datos_semanales = DetalleFactura.objects.filter(factura__fecha__range=[inicio_semana, hoy])
        datos_mensuales = DetalleFactura.objects.filter(factura__fecha__range=[inicio_mes, hoy])

        return Response({
            "diario": calcular_datos(datos_diarios),
            "semanal": calcular_datos(datos_semanales),
            "mensual": calcular_datos(datos_mensuales),
            "moneda": "COP"
        })