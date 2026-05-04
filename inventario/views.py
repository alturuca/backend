import json
from django.utils import timezone
from datetime import timedelta
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.contrib.auth import authenticate
from django.db.models import Sum, F, Count

from django.db.models.functions import TruncDay

from rest_framework import viewsets, permissions, filters,status
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
from inventario.models import Usuario, Producto, Factura, IngresoProducto, DetalleFactura, DetalleIngresoProducto
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
    # 1. Filtramos el queryset inicial para mostrar solo productos activos en la tabla
    queryset = Producto.objects.filter(is_active=True)
    serializer_class = ProductoSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'sku'

    filter_backends = [filters.SearchFilter]
    search_fields = ['sku', 'nombre']
    
    def destroy(self, request, *args, **kwargs):
        """
        En lugar de eliminar físicamente, cambiamos el estado a is_active=False.
        Esto permite conservar el historial de ventas para los reportes de utilidad.
        """
        instance = self.get_object()
        
        # 2. Realizamos la desactivación lógica
        instance.is_active = False
        instance.save()
        
        # 3. Respondemos con éxito (200 OK) para que el frontend actualice la vista
        return Response(
            {"message": "Producto ocultado exitosamente del inventario activo."},
            status=status.HTTP_200_OK
        )


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
        try:
            factura = self.get_object()
            detalles = DetalleFactura.objects.filter(factura=factura)
            
            response = HttpResponse(content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="Factura_{factura.pk}.pdf"'

            p = canvas.Canvas(response, pagesize=letter)
            width, height = letter

            # --- ENCABEZADO (Basado en image_e2681c.png) ---
            p.setFont("Helvetica-Bold", 16)
            p.drawString(50, height - 50, "StocklyX Inc.")
            p.setFont("Helvetica", 10)
            p.drawString(50, height - 65, "Carrera Muelle 38")
            p.drawString(50, height - 77, "Guadalupe- Huila")

            p.setFont("Helvetica-Bold", 14)
            p.drawRightString(width - 50, height - 50, "FACTURA")

            # --- DATOS DE FACTURACIÓN ---
            p.setFont("Helvetica-Bold", 10)
            p.drawString(50, height - 120, "Facturar a")
            p.drawString(250, height - 120, "Enviar a")
            
            p.setFont("Helvetica", 10)
            cliente_nombre = factura.cliente if hasattr(factura, 'cliente') else "Consumidor Final"
            p.drawString(50, height - 135, cliente_nombre)
            p.drawString(50, height - 147, "Dirección General")
            
            p.drawString(250, height - 135, cliente_nombre)
            p.drawString(250, height - 147, "Guadalupe- Huila")

            # --- INFO DE DOCUMENTO (Derecha) ---
            p.setFont("Helvetica-Bold", 10)
            p.drawRightString(450, height - 120, "N° de factura:")
            p.drawRightString(450, height - 132, "Fecha:")
            
            p.setFont("Helvetica", 10)
            p.drawRightString(width - 50, height - 120, f"STX-{factura.pk:03d}")
            p.drawRightString(width - 50, height - 132, factura.fecha.strftime('%d/%m/%Y'))

            # --- TABLA DE PRODUCTOS ---
            y = height - 200
            # Cabecera de tabla
            p.setStrokeColor(colors.lightgrey)
            p.line(50, y + 15, width - 50, y + 15) # Línea superior
            p.setFont("Helvetica-Bold", 9)
            p.drawString(55, y, "CANT.")
            p.drawString(120, y, "DESCRIPCIÓN")
            p.drawRightString(400, y, "PRECIO UNIT.")
            p.drawRightString(width - 55, y, "TOTAL")
            p.line(50, y - 5, width - 50, y - 5) # Línea inferior cabecera

            y -= 20
            total_acumulado = 0
            p.setFont("Helvetica", 9)

            for item in detalles:
                precio = float(item.precio_unitario or 0)
                cantidad = int(item.cantidad or 0)
                importe = precio * cantidad
                total_acumulado += importe
                nombre = item.producto.nombre[:45] if item.producto else "Producto sin nombre"

                p.drawString(55, y, str(cantidad))
                p.drawString(120, y, nombre)
                p.drawRightString(400, y, f"{precio:,.2f}")
                p.drawRightString(width - 55, y, f"{importe:,.2f}")
                
                # Línea tenue entre productos
                p.setStrokeColor(colors.whitesmoke)
                p.line(50, y - 5, width - 50, y - 5)
                y -= 20

            # --- SECCIÓN DE TOTALES EN EL PDF ---
            y -= 10
            p.setStrokeColor(colors.lightgrey)
            p.setFont("Helvetica-Bold", 10)
            
            # Cálculo para el desglose
            subtotal_factura = total_acumulado / 1.19
            valor_iva = total_acumulado - subtotal_factura

            p.drawRightString(450, y, "Subtotal (Base Imponible)")
            p.drawRightString(width - 55, y, f"{subtotal_factura:,.2f}")
            
            y -= 15
            p.drawRightString(450, y, "IVA (19%)")
            p.drawRightString(width - 55, y, f"{valor_iva:,.2f}")

            y -= 25
            # Recuadro de TOTAL FINAL
            p.setFillColor(colors.whitesmoke)
            p.rect(400, y - 10, width - 450, 25, fill=1, stroke=0)
            p.setFillColor(colors.black)
            p.setFont("Helvetica-Bold", 12)
            p.drawRightString(450, y, "TOTAL A PAGAR")
            p.drawRightString(width - 55, y, f"{total_acumulado:,.2f} COP")

            # --- PIE DE PÁGINA (Condiciones) ---
            p.setFont("Helvetica-Bold", 9)
            p.drawString(50, 100, "Condiciones y forma de pago")
            p.setFont("Helvetica", 8)
            p.drawString(50, 88, "El pago se realizará en un plazo de 15 días.")
            p.drawString(50, 76, "Banco: Davivienda Popayán - Cuenta de Ahorros")

            p.showPage()
            p.save()
            return response
        except Exception as e:
            print(f"Error en PDF: {str(e)}")
            return JsonResponse({"error": "Error al generar PDF"}, status=500)

class IngresoProductoViewSet(viewsets.ModelViewSet):
    queryset = IngresoProducto.objects.all()
    serializer_class = IngresoProductoSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        # 1. Guardamos el ingreso principal (Cabecera)
        ingreso = serializer.save()
        
        # 2. Obtenemos los detalles enviados en la petición
        # Se asume que el serializer maneja detalles anidados (Writable Nested Serializer)
        detalles_data = self.request.data.get('detalles', [])
        
        for detalle in detalles_data:
            sku = detalle.get('producto')  # SKU del producto
            cantidad = int(detalle.get('cantidad', 0))
            p_compra = float(detalle.get('precio_compra', 0))
            p_venta = float(detalle.get('precio_venta', 0))
            
            try:
                # 3. Buscamos el producto en la base de datos
                producto = Producto.objects.get(sku=sku)
                
                # 4. ACTUALIZACIÓN DE INVENTARIO
                producto.stock += cantidad          # Incrementamos la cantidad
                producto.precio_compra = p_compra   # Actualizamos costo
                producto.precio_venta = p_venta     # Actualizamos precio final
                
                producto.save() # Guardamos los cambios en la tabla inventario_producto
                
            except Producto.DoesNotExist:
                print(f"Error: El producto con SKU {sku} no existe.")

# --- DASHBOARD Y REPORTES ---

class DashboardStatsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        hoy = timezone.localdate()

        # Helper para calcular base y utilidad consistentes
        def obtener_metricas(queryset):
            total_bruto = queryset.aggregate(
                total=Sum(F('cantidad') * F('precio_unitario')))['total'] or 0
            base_imponible = float(total_bruto) / 1.19
            return {
                "bruto": float(total_bruto),
                "utilidad": base_imponible * 0.40
            }

        stats_hoy = obtener_metricas(DetalleFactura.objects.filter(factura__fecha=hoy))
        stats_mes = obtener_metricas(DetalleFactura.objects.filter(
            factura__fecha__month=hoy.month,
            factura__fecha__year=hoy.year
        ))

        total_stock = Producto.objects.filter(is_active=True).aggregate(total=Sum('stock'))['total'] or 0
        bajo_stock = Producto.objects.filter(is_active=True, stock__lt=10).count()

        return Response({
            "totales": {
                "hoy": stats_hoy["bruto"],
                "mes": stats_mes["bruto"],
                "utilidad": stats_mes["utilidad"],
                "meta_mensual": 10000000,
                "porcentaje_meta": (stats_mes["bruto"] / 10000000) * 100 if stats_mes["bruto"] > 0 else 0
            },
            "stats_cards": [
                {"id": 1, "name": 'Ventas del Día', "value": f"${stats_hoy['bruto']:,.0f}"},
                {"id": 2, "name": 'Productos en Stock', "value": str(total_stock)},
                {"id": 3, "name": 'Bajo Stock', "value": str(bajo_stock)},
            ]
        })

    
class ReporteVentasView(APIView):
    """
    Vista unificada que corrige el error de acumulado en tarjetas.
    Usa la hora local de Colombia para evitar desfases después de las 7 PM.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # ✅ FORZAMOS HORA LOCAL DE COLOMBIA
        # Esto evita que el servidor crea que ya es mañana (UTC)
        ahora_local = timezone.localtime(timezone.now())
        hoy = ahora_local.date()
        
        # Filtros de tiempo usando la fecha local real de Popayán
        query_hoy = DetalleFactura.objects.filter(factura__fecha=hoy)
        query_mes = DetalleFactura.objects.filter(
            factura__fecha__month=hoy.month, 
            factura__fecha__year=hoy.year
        )

        def calcular_totales(queryset):
            res = queryset.aggregate(
                t=Sum(F('cantidad') * F('precio_unitario')), 
                c=Count('factura', distinct=True)
            )
            valor_bruto = float(res['t'] or 0)
            # Cálculo contable: Utilidad 40% sobre la base (Total / 1.19)
            base_imponible = valor_bruto / 1.19
            return {
                "bruto": valor_bruto,
                "conteo": res['c'] or 0,
                "utilidad": base_imponible * 0.40
            }

        data_hoy = calcular_totales(query_hoy)
        data_mes = calcular_totales(query_mes)

        # Tendencia para gráficas (Últimos 28 días)
        hace_28_dias = hoy - timedelta(days=27)
        reporte_db = (
            DetalleFactura.objects
            .filter(factura__fecha__range=[hace_28_dias, hoy])
            .values(fecha_dia=F('factura__fecha'))
            .annotate(ventas=Sum(F('cantidad') * F('precio_unitario')))
            .order_by('fecha_dia')
        )

        return Response({
            "totales": {
                "hoy": data_hoy["bruto"],
                "mes": data_mes["bruto"],
                "utilidad": data_mes["utilidad"]
            },
            "conteo_facturas_mes": data_mes["conteo"],
            "ticket_promedio_mes": data_mes["bruto"] / data_mes["conteo"] if data_mes["conteo"] > 0 else 0,
            "tendencia_semanal": [
                {"nombre": item['fecha_dia'].strftime('%d/%m'), "ventas": float(item['ventas'])} 
                for item in reporte_db
            ],
            "moneda": "COP"
        })

class ReporteUtilidadView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        ahora_local = timezone.localtime(timezone.now())
        hoy = ahora_local.date()
        
        # Inicio de semana (Lunes)
        inicio_semana = hoy - timedelta(days=hoy.weekday())
        # Inicio de mes (Día 1)
        inicio_mes = hoy.replace(day=1)

        def calcular_metrica(queryset):
            res = queryset.aggregate(
                total=Sum(F('cantidad') * F('precio_unitario')), 
                conteo=Count('factura', distinct=True)
            )
            valor_bruto = float(res['total'] or 0)
            subtotal = valor_bruto / 1.19
            return {
                "ventas": valor_bruto,
                "utilidad": subtotal * 0.40,
                "conteo": res['conteo'] or 0
            }

        # --- EL CAMBIO ESTÁ AQUÍ ---
        # Si quieres que la semana NO supere al mes, 
        # el filtro semanal debe empezar en 'inicio_semana' O en 'inicio_mes' (el que sea más reciente)
        punto_inicio_semanal = max(inicio_semana, inicio_mes)

        return Response({
            "diario": calcular_metrica(DetalleFactura.objects.filter(factura__fecha=hoy)),
            "semanal": calcular_metrica(DetalleFactura.objects.filter(
                factura__fecha__range=[punto_inicio_semanal, hoy]
            )),
            "mensual": calcular_metrica(DetalleFactura.objects.filter(
                factura__fecha__range=[inicio_mes, hoy]
            )),
            "moneda": "COP"
        })