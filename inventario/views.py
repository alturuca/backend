import json
from datetime import timedelta
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.contrib.auth import authenticate
from django.db.models import Sum, F, Count
from django.utils import timezone
from django.db.models.functions import TruncDay

from rest_framework import viewsets, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.decorators import action
from rest_framework_simplejwt.tokens import RefreshToken

# Herramientas para PDF (ReportLab)
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors

# Imports relativos del proyecto StocklyX
from inventario.models import Usuario, Producto, Factura, IngresoProducto, DetalleFactura
from inventario.serializers import UsuarioSerializer, ProductoSerializer, FacturaSerializer, IngresoProductoSerializer

# --- AUTENTICACIÓN ---

@method_decorator(csrf_exempt, name='dispatch')
class LoginView(APIView):
    def post(self, request, *args, **kwargs):
        data = request.data
        username = data.get('username')
        password = data.get('password')
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            refresh = RefreshToken.for_user(user)
            return JsonResponse({
                'message': 'Inicio de sesión exitoso',
                'username': user.username,
                'rol': getattr(user, 'rol', 'vendedor'),
                'access_token': str(refresh.access_token),
                'refresh_token': str(refresh)
            })
        return JsonResponse({'error': 'Credenciales inválidas'}, status=401)

class UserDataView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        user = request.user
        return Response({
            'username': user.username,
            'first_name': user.first_name,
            'rol': getattr(user, 'rol', 'vendedor'),
        })

# --- VIEWSETS (CRUD) ---

class UsuarioViewSet(viewsets.ModelViewSet):
    queryset = Usuario.objects.all()
    serializer_class = UsuarioSerializer
    permission_classes = [IsAdminUser]

class ProductoViewSet(viewsets.ModelViewSet):
    queryset = Producto.objects.all()
    serializer_class = ProductoSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'sku'

class FacturaViewSet(viewsets.ModelViewSet):
    queryset = Factura.objects.all().order_by('-fecha')
    serializer_class = FacturaSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = self.queryset
        inicio = self.request.query_params.get('inicio')
        fin = self.request.query_params.get('fin')
        if inicio and fin:
            queryset = queryset.filter(fecha__range=[inicio, fin])
        return queryset

    @action(detail=True, methods=['get'])
    def exportar_pdf(self, request, pk=None):
        """Genera factura en PDF con datos protegidos."""
        try:
            factura = self.get_object()
            detalles = DetalleFactura.objects.filter(factura=factura)
            
            response = HttpResponse(content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="Factura_{factura.pk}.pdf"'

            p = canvas.Canvas(response, pagesize=letter)
            width, height = letter

            # Cabecera
            p.setFillColorRGB(0.12, 0.12, 0.12)
            p.rect(40, 740, 520, 40, fill=1)
            p.setFillColor(colors.white)
            p.setFont("Helvetica-Bold", 18)
            p.drawCentredString(width / 2, 755, "STOCKLYX - COMPROBANTE DE VENTA")

            p.setFillColor(colors.black)
            p.setFont("Helvetica-Bold", 11)
            p.drawString(50, 715, "Popayán, Cauca - Colombia")
            
            p.rect(380, 685, 180, 50)
            p.setFont("Helvetica-Bold", 12)
            p.drawString(390, 720, f"FACTURA N°: {factura.pk}")
            
            # Tabla de Items
            y = 630
            p.setFont("Helvetica-Bold", 10)
            p.drawString(50, y, "DESCRIPCIÓN")
            p.drawString(300, y, "CANT.")
            p.drawRightString(550, y, "SUBTOTAL")
            
            y -= 25
            total_acumulado = 0
            p.setFont("Helvetica", 10)

            for item in detalles:
                precio = item.precio_unitario or 0
                cantidad = item.cantidad or 0
                subtotal = precio * cantidad
                total_acumulado += subtotal
                nombre = item.producto.nombre[:35] if item.producto else "Producto s/n"
                
                p.drawString(50, y, f"{nombre}")
                p.drawString(310, y, f"{cantidad}")
                p.drawRightString(550, y, f"${subtotal:,.0f}")
                y -= 20

            # Total
            p.setFont("Helvetica-Bold", 12)
            p.setFillColor(colors.darkgreen)
            p.drawRightString(550, y - 15, f"TOTAL: ${total_acumulado:,.0f} COP")

            p.showPage()
            p.save()
            return response
        except Exception as e:
            print(f"Error en PDF: {str(e)}")
            return JsonResponse({"error": "Error al generar PDF"}, status=500)

# --- CLASE QUE SOLUCIONA EL IMPORT ERROR ---
class IngresoProductoViewSet(viewsets.ModelViewSet):
    """ViewSet para gestionar la entrada de mercancía (StocklyX)."""
    queryset = IngresoProducto.objects.all()
    serializer_class = IngresoProductoSerializer
    permission_classes = [IsAuthenticated]

# --- DASHBOARD Y REPORTES ---

class DashboardStatsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # 1. Obtener la fecha de hoy asegurando la zona horaria de Colombia
        hoy = timezone.now().date() 

        # 2. Calcular Ventas del Día sumando los detalles de las facturas de hoy
        ventas_dia_query = DetalleFactura.objects.filter(
            factura__fecha=hoy
        ).aggregate(
            total=Sum(F('cantidad') * F('precio_unitario'))
        )
        ventas_dia = ventas_dia_query['total'] or 0

        # 3. Calcular Rendimiento Mensual (Ventas del mes actual)
        ventas_mes_query = DetalleFactura.objects.filter(
            factura__fecha__month=hoy.month,
            factura__fecha__year=hoy.year
        ).aggregate(
            total=Sum(F('cantidad') * F('precio_unitario'))
        )
        ventas_mes = ventas_mes_query['total'] or 0

        # 4. Otros datos (Stock y Alertas)
        total_stock = Producto.objects.aggregate(total=Sum('stock'))['total'] or 0
        bajo_stock = Producto.objects.filter(stock__lt=10).count()

        # Respuesta estructurada para tu frontend en React
        return Response({
            "totales": {
                "hoy": float(ventas_dia),
                "mes": float(ventas_mes),
                "meta_mensual": 10000000, # La meta de 10 millones que se ve en tu imagen
                "porcentaje_meta": (float(ventas_mes) / 10000000) * 100 if ventas_mes > 0 else 0
            },
            "stats_cards": [
                {"id": 1, "name": 'Ventas del Día', "value": f"${float(ventas_dia):,.0f}", "change": 'Hoy', "changeType": 'increase'},
                {"id": 2, "name": 'Productos en Stock', "value": str(total_stock), "change": 'Total items', "changeType": 'neutral'},
                {"id": 3, "name": 'Bajo Stock', "value": str(bajo_stock), "change": 'Revisar', "changeType": 'decrease'},
            ]
        })

class ReporteVentasView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        hoy = timezone.localdate()
        
        # Totales para Reportes.jsx y ReporteVentas.jsx
        ventas_hoy = DetalleFactura.objects.filter(factura__fecha=hoy).aggregate(
            t=Sum(F('cantidad') * F('precio_unitario')))['t'] or 0
        
        ventas_mes_query = DetalleFactura.objects.filter(
            factura__fecha__month=hoy.month,
            factura__fecha__year=hoy.year
        ).aggregate(
            total=Sum(F('cantidad') * F('precio_unitario')),
            conteo=Count('factura', distinct=True)
        )
        
        ventas_mes = float(ventas_mes_query['total'] or 0)
        conteo_facturas = ventas_mes_query['conteo'] or 0

        # Tendencia para las gráficas
        hace_28_dias = hoy - timedelta(days=27)
        reporte_db = (
            DetalleFactura.objects
            .filter(factura__fecha__range=[hace_28_dias, hoy])
            .values(fecha_dia=F('factura__fecha'))
            .annotate(ventas=Sum(F('cantidad') * F('precio_unitario')))
            .order_by('fecha_dia')
        )

        tendencia = [
            {"nombre": item['fecha_dia'].strftime('%d/%m'), "ventas": float(item['ventas'])} 
            for item in reporte_db
        ]

        return Response({
            "totales": { # Llave esperada por Reportes.jsx
                "hoy": float(ventas_hoy),
                "mes": ventas_mes,
                "utilidad": ventas_mes * 0.40
            },
            "ventas_mes": ventas_mes, # Llave para ReporteMensual.jsx
            "conteo_facturas_mes": conteo_facturas,
            "ticket_promedio_mes": ventas_mes / conteo_facturas if conteo_facturas > 0 else 0,
            "tendencia_semanal": tendencia # Para GraficasReporte.jsx
        })
        
class ReporteUtilidadView(APIView):
    permission_classes = [IsAdminUser]
    def get(self, request):
        hoy = timezone.localdate()
        def calcular_datos(queryset):
            res = queryset.aggregate(total=Sum(F('cantidad') * F('precio_unitario')), conteo=Count('factura', distinct=True))
            v = res['total'] or 0
            c = res['conteo'] or 0
            return {"ventas": float(v), "utilidad": float(v) * 0.40, "ticket_promedio": float(v/c) if c > 0 else 0}

        return Response({
            "diario": calcular_datos(DetalleFactura.objects.filter(factura__fecha=hoy)),
            "mensual": calcular_datos(DetalleFactura.objects.filter(factura__fecha__month=hoy.month)),
            "moneda": "COP"
        })