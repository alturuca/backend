from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    LoginView, 
    ProductoViewSet, 
    UserDataView, 
    UsuarioViewSet, 
    FacturaViewSet, 
    IngresoProductoViewSet,
    ReporteVentasView  
)

router = DefaultRouter()
router.register(r'usuarios', UsuarioViewSet)
router.register(r'productos', ProductoViewSet)
router.register(r'facturas', FacturaViewSet)
router.register(r'ingreso', IngresoProductoViewSet)

# <-- BORRÉ LA LÍNEA: router.register(r'reporte-ventas', ReporteVentasView)

urlpatterns = [
    # Autenticación
    path('auth/login/', LoginView.as_view(), name='api_login'),
    path('auth/me/', UserDataView.as_view(), name='user_data'), 
    
    # 2. Nueva ruta para los informes de ventas (COMO PATH INDEPENDIENTE)
    path('reporte-ventas/', ReporteVentasView.as_view(), name='reporte-ventas'),
    

    path('', include(router.urls)),  
]